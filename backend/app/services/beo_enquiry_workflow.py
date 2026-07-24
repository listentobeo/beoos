from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.beo_enquiry import (
    BeoCommissionEnquiryInput,
    BeoCommissionEnquiryOutput,
    CustomerIdentity,
)
from app.domain.email import EmailTriageResult
from app.infrastructure.models import (
    AIExecution,
    ApprovalRequest,
    AuditLog,
    Business,
    Contact,
    EmailAnalysis,
    EmailDraft,
    EmailMessage,
    EmailThread,
    PriceCatalogItem,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)
from app.services.business_context import build_business_context
from app.services.tool_registry import ToolRegistry

WORKFLOW_KEY = "beo_art_commission_enquiry_v1"
REQUIRED_FIELDS = ("requested_service", "medium", "dimensions", "deadline", "location")


async def commission_workflow_allows_external_actions(
    session: AsyncSession, business_id: UUID
) -> bool:
    mode = await session.scalar(
        select(WorkflowDefinition.deployment_mode).where(
            WorkflowDefinition.business_id == business_id,
            WorkflowDefinition.key == WORKFLOW_KEY,
            WorkflowDefinition.status == "active",
        )
    )
    return mode in {"limited_autonomy", "active"}


async def record_commission_enquiry_workflow(
    session: AsyncSession,
    settings: Settings,
    *,
    business: Business,
    contact: Contact | None,
    thread: EmailThread,
    message: EmailMessage,
    channel: Literal["website_form", "gmail", "zoho", "whatsapp", "manual"],
    triage: EmailTriageResult | None = None,
    provider_response_id: str | None = None,
) -> WorkflowRun:
    definition = await _definition(session, business.id)
    idempotency_key = f"{channel}:{message.id}"
    existing = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.business_id == business.id,
            WorkflowRun.workflow_definition_id == definition.id,
            WorkflowRun.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    if triage is None:
        analysis = await session.scalar(
            select(EmailAnalysis).where(EmailAnalysis.message_id == message.id)
        )
        triage_data = _analysis_data(analysis)
        provider_response_id = analysis.response_id if analysis else provider_response_id
    else:
        triage_data = triage.model_dump(mode="json")
    draft = await session.scalar(
        select(EmailDraft)
        .where(EmailDraft.source_message_id == message.id)
        .order_by(EmailDraft.created_at.desc())
    )
    enquiry = _structured_input(contact, message, channel, triage_data)
    run = WorkflowRun(
        business_id=business.id,
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        trigger_type=channel,
        trigger_reference_type="email_message",
        trigger_reference_id=str(message.id),
        correlation_id=f"enquiry:{business.id}:{message.id}",
        idempotency_key=idempotency_key,
        status="running",
        started_at=datetime.now(UTC),
        current_step_key="normalize_input",
        attempt_count=1,
        run_metadata={
            "thread_id": str(thread.id),
            "contact_id": str(contact.id) if contact else None,
            "deployment_mode": definition.deployment_mode,
        },
    )
    session.add(run)
    await session.flush()

    trace: list[dict[str, Any]] = []
    sequence = 1
    input_step = await _step(
        session,
        run,
        "normalize_input",
        "deterministic",
        sequence,
        enquiry.model_dump(mode="json"),
        {"deduplicated_by": idempotency_key, "tenant_id": str(business.id)},
    )
    trace.append(_trace(input_step))

    context = await build_business_context(session, business.id)
    official_prices = await _matching_prices(
        session, business.id, enquiry.requested_service
    )
    deterministic = {
        "customer_match": str(contact.id) if contact else None,
        "business_open_now": _is_business_open(business.timezone),
        "official_price_matches": official_prices,
        "timeline_rule": "rush_requires_approval" if enquiry.urgency else "standard_review",
        "authoritative_context_warnings": context.warnings,
    }
    sequence += 1
    context_step = await _step(
        session,
        run,
        "deterministic_context",
        "deterministic",
        sequence,
        enquiry.model_dump(mode="json"),
        deterministic,
    )
    trace.append(_trace(context_step))

    missing = sorted(set(enquiry.missing_information + _missing_fields(enquiry)))
    structured_analysis = {
        "classification": triage_data.get("category", "general"),
        "intent": triage_data.get("intent", "commission enquiry"),
        "extracted_fields": triage_data.get("extracted_fields", {}),
        "ambiguity_flags": triage_data.get("ambiguity_flags", []),
        "urgency": enquiry.urgency,
        "sentiment": enquiry.sentiment,
        "risk_flags": triage_data.get("risk_flags", []),
        "operational_summary": triage_data.get("operational_summary")
        or str(triage_data.get("intent") or "Enquiry requires review"),
    }
    sequence += 1
    ai_step = await _step(
        session,
        run,
        "ai_judgment",
        "ai",
        sequence,
        enquiry.model_dump(mode="json"),
        structured_analysis,
    )
    session.add(
        AIExecution(
            business_id=business.id,
            workflow_run_id=run.id,
            workflow_step_id=ai_step.id,
            agent_key="beo_commission_enquiry",
            agent_version="1",
            provider=settings.effective_ai_provider,
            model=settings.effective_ai_model,
            prompt_version="email_triage_v1",
            policy_version=definition.policy_version,
            input_schema_version="beo_commission_enquiry_input_v1",
            output_schema_version="beo_commission_enquiry_analysis_v1",
            context_references=[
                {
                    "context_type": item.context_type,
                    "record_id": str(item.record_id) if item.record_id else None,
                    "version": item.version,
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "authority_level": item.authority_level,
                    "approval_status": item.approval_status,
                }
                for item in context.references
            ],
            structured_input=enquiry.model_dump(mode="json"),
            structured_output=structured_analysis,
            provider_response_id=provider_response_id,
            confidence=_confidence(triage_data),
            parse_status="valid" if triage is not None or triage_data else "fallback",
            safety_flags=list(triage_data.get("risk_flags", [])),
        )
    )
    trace.append(_trace(ai_step))

    approval_reasons = _approval_reasons(enquiry, triage_data, official_prices)
    qualification = (
        "unqualified"
        if triage_data.get("recommended_action") == "ignore"
        else "needs_information"
        if missing
        else "qualified"
    )
    policy_result = {
        "passed": not approval_reasons,
        "approval_required": bool(approval_reasons),
        "checks": {
            "official_price_only": True,
            "no_autonomous_discount": True,
            "no_unapproved_commitment": True,
            "mandatory_review_reasons": approval_reasons,
        },
    }
    output = BeoCommissionEnquiryOutput(
        structured_analysis=structured_analysis,
        qualification_recommendation=qualification,
        missing_questions=[f"Please provide {field.replace('_', ' ')}." for field in missing],
        suggested_reply=(
            draft.body_text
            if draft is not None
            else str(triage_data.get("acknowledgement_body") or "A human will review this enquiry.")
        ),
        proposed_crm_update={
            "stage": "qualified" if qualification == "qualified" else "new",
            "service": enquiry.requested_service,
            "temperature": "hot" if enquiry.urgency else "warm",
            "execute": False,
        },
        proposed_follow_up={
            "cadence": "hot" if enquiry.urgency else "standard",
            "execute": False,
        },
        policy_result=policy_result,
        approval_required=bool(approval_reasons),
        approval_reasons=approval_reasons,
        operational_trace=trace,
    )
    sequence += 1
    policy_step = await _step(
        session,
        run,
        "policy_and_approval",
        "policy",
        sequence,
        structured_analysis,
        output.model_dump(mode="json"),
    )
    trace.append(_trace(policy_step))
    output.operational_trace = trace
    policy_step.output_snapshot = output.model_dump(mode="json")

    if approval_reasons:
        tools = await ToolRegistry().sync_definitions(session)
        draft_tool = next((item for item in tools if item.key == "create_draft"), None)
        session.add(
            ApprovalRequest(
                business_id=business.id,
                workflow_run_id=run.id,
                workflow_step_id=policy_step.id,
                proposed_action_type="create_draft",
                proposed_action_payload={
                    "thread_id": str(thread.id),
                    "source_message_id": str(message.id),
                    "subject": draft.subject if draft else f"Re: {thread.subject}",
                    "body_text": output.suggested_reply,
                    "draft_type": draft.draft_type if draft else "manual_follow_up",
                },
                reason="; ".join(approval_reasons),
                decision_summary=structured_analysis["operational_summary"],
                context_references=[
                    {"source_type": item.source_type, "source_id": item.source_id}
                    for item in context.references
                ],
                confidence=_confidence(triage_data),
                risk_level="high"
                if any("legal" in item or "refund" in item for item in approval_reasons)
                else "medium",
                affected_customer_id=contact.id if contact else None,
                requested_tool_id=draft_tool.id if draft_tool else None,
                required_role="manager",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
                original_payload=output.model_dump(mode="json"),
                final_payload=output.model_dump(mode="json"),
            )
        )
        run.status = "waiting_for_approval"
    else:
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
    run.current_step_key = policy_step.step_key
    session.add(
        AuditLog(
            business_id=business.id,
            actor_id="system",
            action="workflow.beo_commission_enquiry.recorded",
            resource_type="workflow_run",
            resource_id=str(run.id),
            details={
                "channel": channel,
                "approval_required": bool(approval_reasons),
                "deployment_mode": definition.deployment_mode,
                "external_action_executed": False,
            },
        )
    )
    await session.flush()
    return run


async def _definition(session: AsyncSession, business_id: UUID) -> WorkflowDefinition:
    definition = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.business_id == business_id,
            WorkflowDefinition.key == WORKFLOW_KEY,
            WorkflowDefinition.version == 1,
        )
    )
    if definition is not None:
        return definition
    definition = WorkflowDefinition(
        business_id=business_id,
        key=WORKFLOW_KEY,
        name="Beo Art Studio commission enquiry",
        description="Bounded intake, analysis, policy, and approval workflow.",
        business_objective="Qualify commission enquiries safely and prepare the next action.",
        workflow_type="enquiry_intake",
        version=1,
        status="active",
        trigger_type="external_event",
        input_schema=BeoCommissionEnquiryInput.model_json_schema(),
        output_schema=BeoCommissionEnquiryOutput.model_json_schema(),
        configuration={
            "supported_triggers": ["website_form", "gmail", "zoho", "whatsapp", "manual"],
            "external_actions": "disabled_in_shadow",
        },
        policy_version="beo_commission_policy_v1",
        prompt_version="email_triage_v1",
        deployment_mode="shadow",
        created_by="system",
    )
    session.add(definition)
    await session.flush()
    return definition


async def _step(
    session: AsyncSession,
    run: WorkflowRun,
    key: str,
    step_type: str,
    sequence: int,
    input_snapshot: dict[str, Any],
    output_snapshot: dict[str, Any],
) -> WorkflowStep:
    now = datetime.now(UTC)
    step = WorkflowStep(
        business_id=run.business_id,
        workflow_run_id=run.id,
        step_key=key,
        step_type=step_type,
        sequence=sequence,
        status="completed",
        input_snapshot=input_snapshot,
        output_snapshot=output_snapshot,
        started_at=now,
        completed_at=now,
    )
    session.add(step)
    await session.flush()
    return step


def _structured_input(
    contact: Contact | None,
    message: EmailMessage,
    channel: Literal["website_form", "gmail", "zoho", "whatsapp", "manual"],
    triage: dict[str, Any],
) -> BeoCommissionEnquiryInput:
    fields = triage.get("extracted_fields")
    fields = fields if isinstance(fields, dict) else {}
    missing = triage.get("missing_information")
    missing = list(missing) if isinstance(missing, list) else []
    return BeoCommissionEnquiryInput(
        customer=CustomerIdentity(
            contact_id=contact.id if contact else None,
            name=contact.name if contact else message.sender_name,
            email=contact.email if contact else message.sender_email,
            phone=contact.phone if contact else None,
            previous_customer=contact.is_existing_client if contact else False,
        ),
        channel=channel,
        message=message.body_text,
        attachments=message.attachment_metadata,
        requested_service=fields.get("service"),
        medium=fields.get("medium"),
        dimensions=fields.get("dimensions"),
        number_of_subjects=fields.get("number_of_subjects"),
        reference_image_available=fields.get("reference_image_available"),
        deadline=fields.get("deadline"),
        location=fields.get("location"),
        framing=fields.get("framing"),
        delivery=fields.get("delivery"),
        budget=fields.get("budget"),
        occasion=fields.get("occasion"),
        urgency=bool(triage.get("urgency")),
        sentiment=triage.get("sentiment"),
        missing_information=[str(item) for item in missing],
    )


def _analysis_data(analysis: EmailAnalysis | None) -> dict[str, Any]:
    if analysis is None:
        return {}
    return {
        "category": analysis.category.value,
        "intent": analysis.intent,
        "confidence": float(analysis.confidence),
        "urgency": analysis.urgency,
        "is_deal": analysis.is_deal,
        "is_professional": analysis.is_professional,
        "risk_flags": analysis.risk_flags,
        "extracted_fields": analysis.extracted_fields,
        "recommended_action": analysis.recommended_action,
    }


async def _matching_prices(
    session: AsyncSession, business_id: UUID, service: str | None
) -> list[dict[str, Any]]:
    if not service:
        return []
    rows = (
        await session.scalars(
            select(PriceCatalogItem)
            .where(
                PriceCatalogItem.business_id == business_id,
                PriceCatalogItem.active.is_(True),
                PriceCatalogItem.service.ilike(f"%{service[:80]}%"),
            )
            .limit(20)
        )
    ).all()
    return [
        {
            "price_id": str(row.id),
            "label": row.label,
            "amount_min": str(row.amount_min) if row.amount_min is not None else None,
            "amount_max": str(row.amount_max) if row.amount_max is not None else None,
            "currency": row.currency,
        }
        for row in rows
    ]


def _missing_fields(enquiry: BeoCommissionEnquiryInput) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not getattr(enquiry, field)]


def _approval_reasons(
    enquiry: BeoCommissionEnquiryInput,
    triage: dict[str, Any],
    official_prices: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    risks = {str(item) for item in triage.get("risk_flags", [])}
    mapping = {
        "discount": "discount request",
        "refund": "refund request",
        "legal": "legal or privacy concern",
        "privacy": "legal or privacy concern",
        "rush": "rush commitment",
        "international_delivery": "international delivery",
        "unusual_materials": "unusual materials",
        "uncertain_reference_quality": "uncertain reference quality",
        "angry_customer": "angry customer",
        "mass_message": "mass message",
        "outside_policy_promise": "promise outside policy",
    }
    reasons.extend(reason for key, reason in mapping.items() if key in risks)
    if "pricing" in risks and not official_prices:
        reasons.append("custom pricing")
    text = enquiry.message.lower()
    if enquiry.urgency or "rush" in text:
        reasons.append("rush commitment")
    if enquiry.sentiment in {"angry", "hostile"} or any(
        word in text for word in ("angry", "furious", "unacceptable")
    ):
        reasons.append("angry customer")
    if "international" in text or "outside nigeria" in text:
        reasons.append("international delivery")
    if "mass message" in text or "bulk message" in text:
        reasons.append("mass message")
    if enquiry.reference_image_available is False and "reference" in text:
        reasons.append("uncertain reference quality")
    if enquiry.medium and enquiry.medium.lower() not in {
        "oil",
        "acrylic",
        "charcoal",
        "pencil",
        "digital",
        "mixed media",
    }:
        reasons.append("unusual materials")
    if ("price" in text or "quote" in text) and not official_prices:
        reasons.append("custom pricing")
    if "promise" in text or "guarantee" in text:
        reasons.append("promise outside policy")
    return sorted(set(reasons))


def _is_business_open(timezone: str) -> bool:
    try:
        local = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        local = datetime.now(UTC)
    return local.weekday() < 5 and 9 <= local.hour < 17


def _confidence(triage: dict[str, Any]) -> Decimal | None:
    value = triage.get("confidence")
    try:
        return Decimal(str(value)) if value is not None else None
    except Exception:
        return None


def _trace(step: WorkflowStep) -> dict[str, Any]:
    return {
        "step_id": str(step.id),
        "step_key": step.step_key,
        "step_type": step.step_type,
        "status": step.status,
    }
