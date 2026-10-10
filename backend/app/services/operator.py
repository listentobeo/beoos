import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import UUID

import httpx
import structlog
from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.operator import OperatorActionSuggestion, OperatorChatResponse, OperatorMode
from app.infrastructure.models import (
    ApprovalRequest,
    AuditLog,
    Business,
    CRMLead,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadStage,
    MarketingMetric,
    OperatorConversation,
    OperatorMessage,
    OperatorTurn,
    Outcome,
    PriceCatalogItem,
    Quote,
    QuoteStatus,
    QuoteTemplate,
    Role,
    ThreadCategory,
    ThreadStatus,
    WorkflowDefinition,
    WorkflowDeployment,
    WorkflowRun,
)
from app.services.business_context import build_business_context
from app.services.replicate_predictions import run_prediction

logger = structlog.get_logger()

OPEN_LEAD_STAGES = {
    LeadStage.new,
    LeadStage.contacted,
    LeadStage.qualified,
    LeadStage.quote_needed,
    LeadStage.quoted,
    LeadStage.deposit_pending,
}

SYSTEM_PROMPT = """
You are BeoOS Operator, a tenant-aware AI operating assistant for SMEs.

You help the user reason over their BeoOS business data: inbox, clients, CRM leads,
pricing/inventory, quotations, analytics, marketing signals, follow-ups, and approvals.

Current safety rules:
- You are in read-and-plan mode. Do not claim you changed data or sent messages.
- If the user asks for a write action, propose it as a needs_confirmation action.
- Stay tenant-aware: only discuss the supplied business context.
- Be practical, specific, and concise.
- Prefer business operating advice over generic motivation.
- If context is missing, say exactly what needs to be connected or configured.
- Keep private customer data short and relevant.
- Label facts, inferences, recommendations, and missing information distinctly.
- Cite only supplied grounding source IDs. Conversation history is not an authoritative source.
- Never invent prices, bypass approval, modify policy/prompt text, or claim external execution.
- Use no more than the supplied bounded tool results; do not request arbitrary tools.

Return only valid JSON matching the expected response schema.
"""

MAX_TOOL_CALLS = 4
LOOP_LIMIT = 2
TURN_TIMEOUT_SECONDS = 30
COST_LIMIT = Decimal("0.050000")

OPERATOR_TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "read_business_profile": {"minimum_role": Role.viewer, "kind": "read"},
    "read_inbox_summary": {"minimum_role": Role.viewer, "kind": "read"},
    "read_crm_summary": {"minimum_role": Role.viewer, "kind": "read"},
    "read_official_pricing": {"minimum_role": Role.viewer, "kind": "read"},
    "read_marketing_metrics": {"minimum_role": Role.viewer, "kind": "read"},
    "read_workflow_status": {"minimum_role": Role.viewer, "kind": "read"},
    "read_value_metrics": {"minimum_role": Role.viewer, "kind": "read"},
    "read_traces_and_failures": {"minimum_role": Role.viewer, "kind": "read"},
    "propose_approval": {"minimum_role": Role.agent, "kind": "propose"},
    "start_workflow": {"minimum_role": Role.agent, "kind": "propose"},
}

ROLE_RANK = {
    Role.viewer: 1,
    Role.agent: 2,
    Role.manager: 3,
    Role.admin: 4,
    Role.owner: 5,
}


class OperatorService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def chat(
        self,
        *,
        session: AsyncSession,
        business_id: UUID,
        user_id: str,
        role: Role,
        message: str,
        mode: OperatorMode,
        conversation_context: list[dict[str, str]],
        conversation_id: UUID | None = None,
    ) -> OperatorChatResponse:
        started = perf_counter()
        conversation = await self._conversation(
            session, business_id, user_id, message, conversation_id
        )
        persisted_context = await self._recent_messages(session, business_id, conversation.id)
        if persisted_context:
            conversation_context = persisted_context
        user_message = OperatorMessage(
            business_id=business_id,
            conversation_id=conversation.id,
            role="user",
            content=message,
            authoritative=False,
        )
        session.add(user_message)
        await session.flush()
        selected_tools = route_operator_tools(message, mode, role)
        context = await self._business_context(session, business_id)
        selected_context = _select_context(context, selected_tools)
        estimated_cost = _estimate_turn_cost(selected_context, message, conversation_context)
        fallback = self._fallback_response(
            context=context,
            message=message,
            mode=mode,
        )
        status = "fallback"
        error_code: str | None = None
        timeout_seconds = (
            max(TURN_TIMEOUT_SECONDS, self._settings.replicate_timeout_seconds)
            if self._settings.effective_ai_provider == "replicate"
            else TURN_TIMEOUT_SECONDS
        )
        if estimated_cost > COST_LIMIT:
            error_code = "ai_budget_exceeded"
            fallback.warnings.append("Operator cost budget prevented a model call.")
            response = fallback
        elif not self._settings.ai_configured:
            error_code = "ai_not_configured"
            fallback.warnings.append(
                "AI provider is not configured; returned deterministic context."
            )
            response = fallback
        else:
            try:
                async with asyncio.timeout(timeout_seconds):
                    response = await self._generate(
                        context=selected_context,
                        message=message,
                        mode=mode,
                        user_id=user_id,
                        conversation_context=conversation_context,
                    )
                selected_tools = model_selected_operator_tools(
                    response.read_only_tools_used, selected_tools, role
                )
                status = "completed"
            except Exception as exc:
                error_code = "ai_timeout" if isinstance(exc, TimeoutError) else "ai_provider_failed"
                if isinstance(exc, httpx.HTTPStatusError):
                    error_code = f"ai_provider_http_{exc.response.status_code}"
                logger.exception(
                    "operator_ai_failed",
                    business_id=str(business_id),
                    mode=mode,
                    error_code=error_code,
                )
                fallback.warnings.append(
                    f"AI generation unavailable ({error_code}); showing business records. "
                    "Check provider credentials, limits and billing."
                )
                response = fallback
        allowed_names = {item["name"] for item in self._tool_manifest()}
        response.recommended_actions = [
            action
            for action in response.recommended_actions
            if action.tool_name is None or action.tool_name in allowed_names
        ]
        sources = _grounding_sources(context, selected_tools)
        response.conversation_id = conversation.id
        response.grounding_sources = sources
        response.read_only_tools_used = [
            key for key in selected_tools if OPERATOR_TOOL_REGISTRY[key]["kind"] == "read"
        ]
        response.statement_labels = _statement_labels(
            response, model_generated=status == "completed"
        )
        duration_ms = int((perf_counter() - started) * 1000)
        response.execution = {
            "selected_tools": selected_tools,
            "tool_call_count": len(selected_tools),
            "max_tool_calls": MAX_TOOL_CALLS,
            "loop_count": 1,
            "loop_limit": LOOP_LIMIT,
            "timeout_seconds": timeout_seconds,
            "status": status,
            "error_code": error_code,
            "cost_limit": str(COST_LIMIT),
            "external_actions_executed": 0,
        }
        assistant_message = OperatorMessage(
            business_id=business_id,
            conversation_id=conversation.id,
            role="operator",
            content=response.answer,
            grounding_sources=sources,
            statement_labels=response.statement_labels,
            tool_activity=[
                {"tool": key, "mode": OPERATOR_TOOL_REGISTRY[key]["kind"]} for key in selected_tools
            ],
            authoritative=False,
        )
        session.add(assistant_message)
        await session.flush()
        session.add(
            OperatorTurn(
                business_id=business_id,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                selected_tools=selected_tools,
                tool_call_count=len(selected_tools),
                max_tool_calls=MAX_TOOL_CALLS,
                loop_count=1,
                loop_limit=LOOP_LIMIT,
                timeout_seconds=timeout_seconds,
                cost_limit=COST_LIMIT,
                estimated_cost=(
                    min(estimated_cost, COST_LIMIT) if status == "completed" else Decimal("0")
                ),
                status=status,
                error_code=error_code,
                duration_ms=duration_ms,
            )
        )
        session.add(
            AuditLog(
                business_id=business_id,
                actor_id=user_id,
                action="operator.turn.completed",
                resource_type="operator_conversation",
                resource_id=str(conversation.id),
                details={
                    "selected_tools": selected_tools,
                    "status": status,
                    "external_actions_executed": 0,
                },
            )
        )
        conversation.updated_at = datetime.now(UTC)
        await session.commit()
        return response

    async def _conversation(
        self,
        session: AsyncSession,
        business_id: UUID,
        user_id: str,
        message: str,
        conversation_id: UUID | None,
    ) -> OperatorConversation:
        conversation = (
            await session.scalar(
                select(OperatorConversation).where(
                    OperatorConversation.id == conversation_id,
                    OperatorConversation.business_id == business_id,
                    OperatorConversation.user_id == user_id,
                    OperatorConversation.status == "active",
                )
            )
            if conversation_id
            else None
        )
        if conversation_id and conversation is None:
            raise ValueError("Tenant operator conversation not found")
        if conversation is None:
            conversation = OperatorConversation(
                business_id=business_id,
                user_id=user_id,
                title=message[:240],
                status="active",
            )
            session.add(conversation)
            await session.flush()
        return conversation

    async def _recent_messages(
        self,
        session: AsyncSession,
        business_id: UUID,
        conversation_id: UUID,
    ) -> list[dict[str, str]]:
        messages = (
            await session.scalars(
                select(OperatorMessage)
                .where(
                    OperatorMessage.business_id == business_id,
                    OperatorMessage.conversation_id == conversation_id,
                )
                .order_by(OperatorMessage.created_at.desc())
                .limit(6)
            )
        ).all()
        return [{"role": row.role, "content": row.content} for row in reversed(messages)]

    async def _business_context(
        self,
        session: AsyncSession,
        business_id: UUID,
    ) -> dict[str, Any]:
        business = await session.scalar(select(Business).where(Business.id == business_id))
        now = datetime.now(UTC)
        since = now - timedelta(days=30)

        totals = {
            "threads": await _count(
                session,
                EmailThread.id,
                EmailThread.business_id == business_id,
            ),
            "unread": int(
                await session.scalar(
                    select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
                        EmailThread.business_id == business_id
                    )
                )
                or 0
            ),
            "needs_approval": await _count(
                session,
                EmailThread.id,
                EmailThread.business_id == business_id,
                EmailThread.status == ThreadStatus.needs_approval,
            ),
            "spam_noise": await _count(
                session,
                EmailThread.id,
                EmailThread.business_id == business_id,
                EmailThread.category == ThreadCategory.spam,
            ),
            "open_leads": await _count(
                session,
                CRMLead.id,
                CRMLead.business_id == business_id,
                CRMLead.stage.in_(OPEN_LEAD_STAGES),
            ),
            "quotes_open": await _count(
                session,
                Quote.id,
                Quote.business_id == business_id,
                Quote.status.in_(
                    {
                        QuoteStatus.draft,
                        QuoteStatus.needs_approval,
                        QuoteStatus.approved,
                        QuoteStatus.sent,
                    }
                ),
            ),
            "due_followups": await _count(
                session,
                FollowUpTask.id,
                FollowUpTask.business_id == business_id,
                FollowUpTask.status == FollowUpStatus.scheduled,
                FollowUpTask.scheduled_for <= now,
            ),
            "marketing_rows_30d": await _count(
                session,
                MarketingMetric.id,
                MarketingMetric.business_id == business_id,
                MarketingMetric.created_at >= since,
            ),
        }

        recent_threads = (
            await session.scalars(
                select(EmailThread)
                .where(EmailThread.business_id == business_id)
                .order_by(EmailThread.latest_message_at.desc())
                .limit(8)
            )
        ).all()
        leads = (
            await session.scalars(
                select(CRMLead)
                .where(CRMLead.business_id == business_id)
                .order_by(CRMLead.lead_score.desc(), CRMLead.updated_at.desc())
                .limit(8)
            )
        ).all()
        prices = (
            await session.scalars(
                select(PriceCatalogItem)
                .where(
                    PriceCatalogItem.business_id == business_id,
                    PriceCatalogItem.active.is_(True),
                )
                .order_by(PriceCatalogItem.service, PriceCatalogItem.label)
                .limit(12)
            )
        ).all()
        templates = (
            await session.scalars(
                select(QuoteTemplate)
                .where(QuoteTemplate.business_id == business_id, QuoteTemplate.active.is_(True))
                .order_by(QuoteTemplate.updated_at.desc())
                .limit(8)
            )
        ).all()
        quotes = (
            await session.scalars(
                select(Quote)
                .where(Quote.business_id == business_id)
                .order_by(Quote.updated_at.desc())
                .limit(8)
            )
        ).all()
        marketing_sources = (
            await session.execute(
                select(MarketingMetric.source, func.count(MarketingMetric.id))
                .where(MarketingMetric.business_id == business_id)
                .group_by(MarketingMetric.source)
                .order_by(func.count(MarketingMetric.id).desc())
            )
        ).all()
        authoritative = await build_business_context(session, business_id)
        workflow_runs = (
            await session.execute(
                select(
                    WorkflowRun.id,
                    WorkflowDefinition.key,
                    WorkflowRun.status,
                    WorkflowRun.last_error_code,
                    WorkflowRun.created_at,
                )
                .join(
                    WorkflowDefinition,
                    WorkflowDefinition.id == WorkflowRun.workflow_definition_id,
                )
                .where(WorkflowRun.business_id == business_id)
                .order_by(WorkflowRun.created_at.desc())
                .limit(12)
            )
        ).all()
        deployments = (
            await session.scalars(
                select(WorkflowDeployment)
                .where(WorkflowDeployment.business_id == business_id)
                .order_by(WorkflowDeployment.created_at.desc())
                .limit(8)
            )
        ).all()
        outcome_totals = (
            await session.execute(
                select(Outcome.outcome_type, func.count(Outcome.id))
                .where(Outcome.business_id == business_id)
                .group_by(Outcome.outcome_type)
            )
        ).all()
        approval_totals = (
            await session.execute(
                select(ApprovalRequest.status, func.count(ApprovalRequest.id))
                .where(ApprovalRequest.business_id == business_id)
                .group_by(ApprovalRequest.status)
            )
        ).all()

        return {
            "business": {
                "id": str(business.id) if business else str(business_id),
                "name": business.name if business else "Unknown business",
                "primary_email": business.primary_email if business else "",
                "timezone": business.timezone if business else "Africa/Lagos",
                "settings": _safe_json(business.settings if business else {}),
            },
            "totals": totals,
            "recent_threads": [
                {
                    "id": str(thread.id),
                    "subject": thread.subject,
                    "category": thread.category.value,
                    "status": thread.status.value,
                    "unread_count": thread.unread_count,
                    "is_deal": thread.is_deal,
                    "latest_message_at": thread.latest_message_at.isoformat(),
                }
                for thread in recent_threads
            ],
            "crm_leads": [
                {
                    "id": str(lead.id),
                    "title": lead.title,
                    "stage": lead.stage.value,
                    "temperature": lead.temperature.value,
                    "lead_score": lead.lead_score,
                    "service": lead.service,
                    "budget": lead.budget,
                    "deadline": lead.deadline,
                    "summary": lead.qualification_summary,
                    "next_follow_up_at": lead.next_follow_up_at.isoformat()
                    if lead.next_follow_up_at
                    else None,
                }
                for lead in leads
            ],
            "price_catalogue_sample": [
                {
                    "id": str(item.id),
                    "service": item.service,
                    "label": item.label,
                    "amount_min": _decimal(item.amount_min),
                    "amount_max": _decimal(item.amount_max),
                    "currency": item.currency,
                    "stock_quantity": item.stock_quantity,
                    "custom_fields": _safe_json(item.custom_fields),
                }
                for item in prices
            ],
            "quote_templates": [
                {
                    "id": str(template.id),
                    "name": template.name,
                    "type": template.template_type.value,
                    "description": template.description,
                    "design_settings": _safe_json(template.design_settings),
                }
                for template in templates
            ],
            "recent_quotes": [
                {
                    "id": str(quote.id),
                    "title": quote.title,
                    "status": quote.status.value,
                    "total": _decimal(quote.total),
                    "currency": quote.currency,
                    "payment_url_configured": bool(quote.payment_url),
                }
                for quote in quotes
            ],
            "marketing_sources": [
                {"source": source, "rows": int(count or 0)} for source, count in marketing_sources
            ],
            "authoritative_context": [
                {
                    "source_id": reference.source_id,
                    "context_type": reference.context_type,
                    "classification": reference.classification,
                    "authority_level": reference.authority_level,
                    "approval_status": reference.approval_status,
                    "data": _safe_json(reference.data),
                }
                for reference in authoritative.references
            ],
            "context_warnings": authoritative.warnings,
            "workflow_status": [
                {
                    "run_id": str(run_id),
                    "workflow_key": workflow_key,
                    "status": status,
                    "last_error_code": error_code,
                    "created_at": created_at.isoformat(),
                }
                for run_id, workflow_key, status, error_code, created_at in workflow_runs
            ],
            "deployments": [
                {
                    "id": str(item.id),
                    "workflow_key": item.workflow_key,
                    "version": item.deployed_version,
                    "mode": item.deployment_mode,
                    "status": item.status,
                }
                for item in deployments
            ],
            "outcome_totals": [
                {"outcome_type": outcome_type, "count": int(count or 0)}
                for outcome_type, count in outcome_totals
            ],
            "approval_totals": [
                {"status": status, "count": int(count or 0)} for status, count in approval_totals
            ],
        }

    async def _generate(
        self,
        *,
        context: dict[str, Any],
        message: str,
        mode: OperatorMode,
        user_id: str,
        conversation_context: list[dict[str, str]],
    ) -> OperatorChatResponse:
        payload = {
            "mode": mode,
            "user_message": message,
            "conversation_context": conversation_context[-6:],
            "beoos_context": context,
            "available_tools": self._tool_manifest(),
        }
        if self._settings.effective_ai_provider == "replicate":
            return await self._replicate(payload=payload, user_id=user_id)
        return await self._openai(payload=payload, user_id=user_id)

    async def _openai(self, *, payload: dict[str, Any], user_id: str) -> OperatorChatResponse:
        if not self._settings.openai_api_key:
            raise RuntimeError("OpenAI API key is not configured")
        client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        try:
            response = await client.responses.parse(
                model=self._settings.openai_model,
                instructions=SYSTEM_PROMPT,
                input=json.dumps(payload, ensure_ascii=False),
                reasoning={"effort": "low"},
                text_format=OperatorChatResponse,
                verbosity="low",
                store=False,
                safety_identifier=hashlib.sha256(user_id.encode()).hexdigest()[:64],
            )
            if response.output_parsed is None:
                raise RuntimeError("OpenAI returned no operator output")
            return response.output_parsed
        finally:
            await client.close()

    async def _replicate(self, *, payload: dict[str, Any], user_id: str) -> OperatorChatResponse:
        if not self._settings.replicate_api_token:
            raise RuntimeError("Replicate API token is not configured")
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Response JSON schema:\n"
            f"{json.dumps(OperatorChatResponse.model_json_schema(), ensure_ascii=False)}\n\n"
            "Payload:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        input_payload = {
            "prompt": prompt,
            "system_prompt": "You are BeoOS Operator. Return only valid JSON.",
            "reasoning_effort": "low",
            "verbosity": "low",
            "max_completion_tokens": 1600,
        }
        async with httpx.AsyncClient(timeout=self._settings.replicate_timeout_seconds) as client:
            prediction = await run_prediction(
                client,
                token=self._settings.replicate_api_token,
                model=self._settings.replicate_model,
                inputs=input_payload,
                timeout_seconds=self._settings.replicate_timeout_seconds,
            )
        output = prediction.get("output")
        text = _stringify_output(output)
        try:
            return OperatorChatResponse.model_validate_json(text)
        except ValidationError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                raise RuntimeError("Replicate returned invalid operator JSON") from None
            return OperatorChatResponse.model_validate_json(text[start:end])

    def _fallback_response(
        self,
        *,
        context: dict[str, Any],
        message: str,
        mode: OperatorMode,
    ) -> OperatorChatResponse:
        totals = context["totals"]
        business = context["business"]
        actions: list[OperatorActionSuggestion] = []
        if totals["needs_approval"]:
            actions.append(
                OperatorActionSuggestion(
                    label="Review pending approval messages",
                    kind="read_only",
                    reason=f"{totals['needs_approval']} thread(s) need human approval.",
                    tool_name="read_inbox_summary",
                    payload={"status": "needs_approval"},
                )
            )
        if totals["due_followups"]:
            actions.append(
                OperatorActionSuggestion(
                    label="Review due follow-ups",
                    kind="read_only",
                    reason=f"{totals['due_followups']} follow-up task(s) are due now.",
                    tool_name="read_crm_summary",
                    payload={"status": "due"},
                )
            )
        if "quote" in message.lower() or mode == "quotes":
            actions.append(
                OperatorActionSuggestion(
                    label="Prepare an AI quote draft",
                    kind="needs_confirmation",
                    reason=(
                        "Quote drafting can now use CRM, price catalogue, templates, "
                        "and tenant instructions."
                    ),
                    tool_name="propose_approval",
                    payload={"action": "create_quotation_draft", "requires_review": True},
                )
            )
        if "marketing" in message.lower() or mode == "marketing":
            actions.append(
                OperatorActionSuggestion(
                    label="Connect Search Console, Blogger, and Clarity",
                    kind="needs_confirmation",
                    reason="Marketing intelligence needs tenant-owned traffic and behavior data.",
                    tool_name="read_marketing_metrics",
                    payload={"requires_tenant_connection": True},
                )
            )
        return OperatorChatResponse(
            answer=(
                f"I can see {business['name']} has {totals['threads']} inbox thread(s), "
                f"{totals['open_leads']} open CRM lead(s), {totals['quotes_open']} open quote(s), "
                f"and {totals['marketing_rows_30d']} marketing data row(s) from the last 30 days. "
                "I am currently in safe read-and-plan mode, so I can analyse and recommend actions "
                "without changing records yet."
            ),
            summary=[
                f"Unread inbox threads/messages count signal: {totals['unread']}",
                f"Needs approval: {totals['needs_approval']}",
                f"Spam/noise already identified: {totals['spam_noise']}",
                "Active price catalogue sample size loaded: "
                f"{len(context['price_catalogue_sample'])}",
            ],
            recommended_actions=actions,
            read_only_tools_used=[
                "business_context",
                "inbox_summary",
                "crm_summary",
                "quote_summary",
            ],
        )

    def _tool_manifest(self) -> list[dict[str, str]]:
        return [
            {
                "name": name,
                "mode": "read_only" if item["kind"] == "read" else "approval_required",
            }
            for name, item in OPERATOR_TOOL_REGISTRY.items()
        ]


async def _count(
    session: AsyncSession,
    column: Any,
    *conditions: Any,
) -> int:
    value = await session.scalar(select(func.count(column)).where(*conditions))
    return int(value or 0)


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _safe_json(value: Any) -> Any:
    return json.loads(json.dumps(value or {}, default=str))


def _stringify_output(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "".join(str(part) for part in output)
    return json.dumps(output, ensure_ascii=False)


def route_operator_tools(message: str, mode: OperatorMode, role: Role) -> list[str]:
    lower = message.lower()
    selected = ["read_business_profile"]
    routes = (
        (
            "read_traces_and_failures",
            any(word in lower for word in ("trace", "fail", "error", "why", "retry")),
        ),
        (
            "read_official_pricing",
            mode == "pricing"
            or any(word in lower for word in ("price", "pricing", "cost", "catalogue")),
        ),
        (
            "read_crm_summary",
            mode == "crm" or any(word in lower for word in ("lead", "crm", "client", "follow up")),
        ),
        (
            "read_inbox_summary",
            mode == "inbox"
            or any(word in lower for word in ("inbox", "email", "message", "reply")),
        ),
        (
            "read_marketing_metrics",
            mode == "marketing"
            or any(word in lower for word in ("marketing", "search console", "traffic")),
        ),
        (
            "read_value_metrics",
            mode == "analytics"
            or any(word in lower for word in ("metric", "value", "revenue", "performance")),
        ),
        (
            "read_workflow_status",
            any(word in lower for word in ("workflow", "run", "deployment", "automation")),
        ),
    )
    for name, matches in routes:
        if matches:
            selected.append(name)
    if len(selected) == 1:
        selected.extend(["read_workflow_status", "read_value_metrics", "read_inbox_summary"])
    return [
        name
        for name in selected
        if ROLE_RANK[role] >= ROLE_RANK[OPERATOR_TOOL_REGISTRY[name]["minimum_role"]]
    ][:MAX_TOOL_CALLS]


def model_selected_operator_tools(
    requested: list[str], candidates: list[str], role: Role
) -> list[str]:
    permitted = {
        name
        for name, specification in OPERATOR_TOOL_REGISTRY.items()
        if specification["kind"] == "read"
        and ROLE_RANK[role] >= ROLE_RANK[specification["minimum_role"]]
    }
    selected = ["read_business_profile"]
    selected.extend(
        name
        for name in requested
        if name in candidates and name in permitted and name not in selected
    )
    if len(selected) == 1:
        selected.extend(name for name in candidates if name not in selected)
    return selected[:MAX_TOOL_CALLS]


def _select_context(context: dict[str, Any], tools: list[str]) -> dict[str, Any]:
    selected: dict[str, Any] = {
        "business": context["business"],
        "authoritative_context": context["authoritative_context"],
        "context_warnings": context["context_warnings"],
    }
    mappings = {
        "read_inbox_summary": ("totals", "recent_threads"),
        "read_crm_summary": ("totals", "crm_leads"),
        "read_official_pricing": ("price_catalogue_sample",),
        "read_marketing_metrics": ("marketing_sources",),
        "read_workflow_status": ("workflow_status", "deployments"),
        "read_value_metrics": ("outcome_totals", "approval_totals", "totals"),
        "read_traces_and_failures": ("workflow_status",),
    }
    for tool in tools:
        for key in mappings.get(tool, ()):
            selected[key] = context[key]
    return selected


def _grounding_sources(context: dict[str, Any], tools: list[str]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for reference in context["authoritative_context"][:20]:
        sources.append(
            {
                "source_id": reference["source_id"],
                "source_type": reference["context_type"],
                "classification": reference["classification"],
                "authority": reference["authority_level"],
            }
        )
    if "read_inbox_summary" in tools:
        sources.append(
            {
                "source_id": "email_threads:tenant_summary",
                "source_type": "recent_communication",
                "classification": "operational_fact",
                "authority": "database",
            }
        )
    if "read_crm_summary" in tools:
        sources.append(
            {
                "source_id": "crm_leads:tenant_summary",
                "source_type": "crm",
                "classification": "operational_fact",
                "authority": "database",
            }
        )
    for tool, source_type in (
        ("read_marketing_metrics", "marketing_metric"),
        ("read_workflow_status", "workflow_run"),
        ("read_value_metrics", "workflow_outcome"),
        ("read_traces_and_failures", "workflow_trace"),
    ):
        if tool in tools:
            sources.append(
                {
                    "source_id": f"{source_type}:tenant_summary",
                    "source_type": source_type,
                    "classification": "operational_fact",
                    "authority": "database",
                }
            )
    return sources[:30]


def _statement_labels(
    response: OperatorChatResponse, *, model_generated: bool
) -> list[dict[str, str]]:
    labels = [
        {
            "type": "inference" if model_generated else "fact",
            "text": response.answer[:500],
        }
    ]
    labels.extend(
        {
            "type": "inference" if model_generated else "fact",
            "text": item[:500],
        }
        for item in response.summary[:6]
    )
    labels.extend(
        {"type": "recommendation", "text": item.label[:500]}
        for item in response.recommended_actions[:6]
    )
    if response.warnings:
        labels.extend(
            {"type": "missing_information", "text": item[:500]} for item in response.warnings[:4]
        )
    return labels


def _estimate_turn_cost(
    context: dict[str, Any],
    message: str,
    conversation_context: list[dict[str, str]],
) -> Decimal:
    characters = len(json.dumps(context, default=str)) + len(message)
    characters += sum(len(item.get("content", "")) for item in conversation_context[-6:])
    estimated_tokens = Decimal(characters) / Decimal("4") + Decimal("1600")
    return (estimated_tokens / Decimal("1000000") * Decimal("10")).quantize(Decimal("0.000001"))
