import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
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
    Business,
    CRMLead,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadStage,
    MarketingMetric,
    PriceCatalogItem,
    Quote,
    QuoteStatus,
    QuoteTemplate,
    ThreadCategory,
    ThreadStatus,
)

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

Return only valid JSON matching the expected response schema.
"""


class OperatorService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def chat(
        self,
        *,
        session: AsyncSession,
        business_id: UUID,
        user_id: str,
        message: str,
        mode: OperatorMode,
        conversation_context: list[dict[str, str]],
    ) -> OperatorChatResponse:
        context = await self._business_context(session, business_id)
        fallback = self._fallback_response(
            context=context,
            message=message,
            mode=mode,
        )
        if not self._settings.ai_configured:
            fallback.warnings.append(
                "AI provider is not configured; returned deterministic context."
            )
            return fallback
        try:
            return await self._generate(
                context=context,
                message=message,
                mode=mode,
                user_id=user_id,
                conversation_context=conversation_context,
            )
        except Exception:
            logger.exception("operator_ai_failed", business_id=str(business_id), mode=mode)
            fallback.warnings.append("AI operator failed; returned deterministic context.")
            return fallback

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
                {"source": source, "rows": int(count or 0)}
                for source, count in marketing_sources
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
        owner, model = self._settings.replicate_model.split("/", maxsplit=1)
        url = f"https://api.replicate.com/v1/models/{owner}/{model}/predictions"
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
        headers = {
            "Authorization": f"Bearer {self._settings.replicate_api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait=10",
        }
        async with httpx.AsyncClient(timeout=self._settings.replicate_timeout_seconds) as client:
            response = await client.post(
                url,
                headers=headers,
                json={
                    "input": input_payload,
                    "context": {
                        "safety_identifier": hashlib.sha256(user_id.encode()).hexdigest()[:64],
                    },
                },
            )
            if response.status_code == 422:
                response = await client.post(url, headers=headers, json={"input": input_payload})
            response.raise_for_status()
            prediction = response.json()
            output = await self._poll_replicate(client, str(prediction["id"]))
        text = _stringify_output(output)
        try:
            return OperatorChatResponse.model_validate_json(text)
        except ValidationError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                raise RuntimeError("Replicate returned invalid operator JSON") from None
            return OperatorChatResponse.model_validate_json(text[start:end])

    async def _poll_replicate(self, client: httpx.AsyncClient, prediction_id: str) -> Any:
        attempts = max(1, self._settings.replicate_timeout_seconds // 3)
        for _ in range(attempts):
            response = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {self._settings.replicate_api_token}"},
            )
            response.raise_for_status()
            prediction = response.json()
            if prediction.get("status") == "succeeded":
                return prediction.get("output")
            if prediction.get("status") in {"failed", "canceled"}:
                raise RuntimeError(f"Replicate prediction {prediction.get('status')}")
        raise RuntimeError("Replicate prediction timed out")

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
                    tool_name="list_inbox_threads",
                    payload={"status": "needs_approval"},
                )
            )
        if totals["due_followups"]:
            actions.append(
                OperatorActionSuggestion(
                    label="Review due follow-ups",
                    kind="read_only",
                    reason=f"{totals['due_followups']} follow-up task(s) are due now.",
                    tool_name="list_followups",
                    payload={"status": "due"},
                )
            )
        if "quote" in message.lower() or mode == "quotes":
            actions.append(
                OperatorActionSuggestion(
                    label="Prepare an AI quote draft",
                    kind="future_tool",
                    reason="Quote generation will use CRM, price catalogue, template, and uploads.",
                    tool_name="create_quote_draft",
                )
            )
        if "marketing" in message.lower() or mode == "marketing":
            actions.append(
                OperatorActionSuggestion(
                    label="Connect Search Console, Blogger, and Clarity",
                    kind="future_tool",
                    reason="Marketing intelligence needs tenant-owned traffic and behavior data.",
                    tool_name="connect_marketing_sources",
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
            {"name": "list_inbox_threads", "mode": "read_only"},
            {"name": "get_thread", "mode": "read_only"},
            {"name": "list_crm_leads", "mode": "read_only"},
            {"name": "list_price_items", "mode": "read_only"},
            {"name": "list_quotes", "mode": "read_only"},
            {"name": "get_marketing_summary", "mode": "read_only"},
            {"name": "create_price_item", "mode": "needs_confirmation"},
            {"name": "create_quote_draft", "mode": "needs_confirmation"},
            {"name": "schedule_followup", "mode": "needs_confirmation"},
            {"name": "send_email_reply", "mode": "needs_confirmation"},
            {"name": "send_whatsapp_message", "mode": "needs_confirmation"},
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
