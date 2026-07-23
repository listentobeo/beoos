import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import (
    ApprovalRequest,
    AuditLog,
    Business,
    BusinessPolicy,
    BusinessProfile,
    Contact,
    CRMLead,
    DraftStatus,
    EmailDraft,
    EmailMessage,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadSource,
    LeadStage,
    LeadTemperature,
    MarketingMetric,
    PriceCatalogItem,
    Quote,
    QuoteStatus,
    QuoteTemplateType,
    Role,
    ToolCall,
    ToolDefinition,
    ToolPermission,
    WorkflowRun,
    WorkflowStep,
)
from app.services.follow_up_scheduler import standard_follow_up_offsets
from app.services.quote_engine import calculate_quote

ToolHandler = Callable[
    [AsyncSession, UUID, dict[str, Any], str], Awaitable[dict[str, Any]]
]


@dataclass(frozen=True)
class ToolSpec:
    key: str
    name: str
    description: str
    risk_level: str
    is_external: bool
    is_reversible: bool
    requires_approval: bool
    required_role: Role
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    idempotency_strategy: str = "tenant-scoped caller key plus request hash"
    timeout_seconds: int = 30
    retry_policy: str = "none"
    failure_mapping: dict[str, str] | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.failure_mapping is None:
            object.__setattr__(
                self,
                "failure_mapping",
                {
                    "PermissionError": "authorization",
                    "ValueError": "validation",
                    "TimeoutError": "transient_failure",
                    "Exception": "permanent_failure",
                },
            )


OBJECT_SCHEMA = {"type": "object", "additionalProperties": False}
ID_SCHEMA = {
    "type": "object",
    "properties": {"id": {"type": "string", "format": "uuid"}},
    "required": ["id"],
    "additionalProperties": False,
}

TOOL_SPECS = (
    ToolSpec(
        "create_crm_lead",
        "Create CRM lead",
        "Create a tenant-owned CRM lead after validating referenced records.",
        "medium",
        False,
        True,
        True,
        Role.admin,
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "contact_id": {"type": "string"},
                "thread_id": {"type": "string"},
                "service": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "update_crm_stage",
        "Update CRM stage",
        "Move a tenant-owned CRM lead to an explicit supported stage.",
        "medium",
        False,
        True,
        True,
        Role.admin,
        {
            "type": "object",
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "stage": {"type": "string", "enum": [item.value for item in LeadStage]},
            },
            "required": ["id", "stage"],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "create_draft",
        "Create communication draft",
        "Create a reviewable draft in a tenant-owned conversation.",
        "medium",
        False,
        True,
        True,
        Role.agent,
        {
            "type": "object",
            "properties": {
                "thread_id": {"type": "string", "format": "uuid"},
                "source_message_id": {"type": "string", "format": "uuid"},
                "subject": {"type": "string"},
                "body_text": {"type": "string"},
                "draft_type": {"type": "string"},
            },
            "required": [
                "thread_id",
                "source_message_id",
                "subject",
                "body_text",
                "draft_type",
            ],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "read_business_profile",
        "Read business profile",
        "Read authoritative identity and operating settings for this tenant.",
        "low",
        False,
        True,
        False,
        Role.viewer,
        OBJECT_SCHEMA,
        {"type": "object"},
    ),
    ToolSpec(
        "create_quotation_draft",
        "Create quotation draft",
        "Persist a deterministic quote calculation as a reviewable tenant draft.",
        "medium",
        False,
        True,
        True,
        Role.admin,
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "template_type": {"type": "string", "enum": ["mural", "custom"]},
                "input_data": {"type": "object"},
                "lead_id": {"type": "string"},
                "contact_id": {"type": "string"},
                "currency": {"type": "string"},
            },
            "required": ["title", "template_type", "input_data"],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "read_brand_policy",
        "Read brand policy",
        "Read the tenant's approved AI and communication policy.",
        "low",
        False,
        True,
        False,
        Role.viewer,
        OBJECT_SCHEMA,
        {"type": "object"},
    ),
    ToolSpec(
        "schedule_follow_up",
        "Schedule follow-up",
        "Replace a lead's pending sequence with the selected deterministic cadence.",
        "medium",
        False,
        True,
        True,
        Role.admin,
        {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "format": "uuid"},
                "cadence": {
                    "type": "string",
                    "enum": ["standard", "hot", "gentle"],
                },
            },
            "required": ["lead_id", "cadence"],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "read_official_pricing",
        "Read official pricing",
        "Read active, approved tenant price records. AI must not calculate official prices.",
        "low",
        False,
        True,
        False,
        Role.viewer,
        {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "read_crm_contact",
        "Read CRM contact",
        "Read one tenant-owned customer record.",
        "medium",
        False,
        True,
        False,
        Role.agent,
        ID_SCHEMA,
        {"type": "object"},
    ),
    ToolSpec(
        "read_recent_conversation",
        "Read recent conversation",
        "Read recent messages from one tenant-owned thread.",
        "medium",
        False,
        True,
        False,
        Role.agent,
        ID_SCHEMA,
        {"type": "object"},
    ),
    ToolSpec(
        "calculate_quotation",
        "Calculate quotation",
        "Run the deterministic quote engine with reviewed input.",
        "medium",
        False,
        True,
        False,
        Role.agent,
        {
            "type": "object",
            "properties": {
                "template_type": {"type": "string", "enum": ["mural", "custom"]},
                "input_data": {"type": "object"},
            },
            "required": ["template_type", "input_data"],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "read_marketing_metrics",
        "Read marketing metrics",
        "Read tenant-scoped imported marketing evidence.",
        "low",
        False,
        True,
        False,
        Role.viewer,
        {
            "type": "object",
            "properties": {"source": {"type": "string"}},
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
    ToolSpec(
        "request_human_approval",
        "Request human approval",
        "Create a structured approval request for a proposed action.",
        "medium",
        False,
        True,
        False,
        Role.agent,
        {
            "type": "object",
            "properties": {
                "proposed_action_type": {"type": "string"},
                "proposed_action_payload": {"type": "object"},
                "reason": {"type": "string"},
                "decision_summary": {"type": "string"},
                "risk_level": {"type": "string"},
                "required_role": {"type": "string"},
            },
            "required": [
                "proposed_action_type",
                "proposed_action_payload",
                "reason",
                "risk_level",
                "required_role",
            ],
            "additionalProperties": False,
        },
        {"type": "object"},
    ),
)

FUTURE_CONTROLLED_SPECS = (
    ("send_approved_email", "Send approved email", "high", True, False),
    ("send_approved_whatsapp", "Send approved WhatsApp", "high", True, False),
    ("create_paystack_payment_link", "Create Paystack payment link", "high", True, False),
    ("create_marketing_recommendation", "Create marketing recommendation", "low", False, True),
    ("fetch_search_console_data", "Fetch Search Console data", "medium", True, True),
)

PERMISSION_RANK = {"read": 1, "propose": 2, "execute": 3}
ROLE_RANK = {
    Role.viewer: 1,
    Role.agent: 2,
    Role.admin: 3,
    Role.owner: 4,
}


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {
            "read_business_profile": self._read_business_profile,
            "read_brand_policy": self._read_brand_policy,
            "read_official_pricing": self._read_official_pricing,
            "read_crm_contact": self._read_crm_contact,
            "read_recent_conversation": self._read_recent_conversation,
            "create_crm_lead": self._create_crm_lead,
            "update_crm_stage": self._update_crm_stage,
            "create_draft": self._create_draft,
            "calculate_quotation": self._calculate_quotation,
            "create_quotation_draft": self._create_quotation_draft,
            "schedule_follow_up": self._schedule_follow_up,
            "read_marketing_metrics": self._read_marketing_metrics,
        }

    async def sync_definitions(self, session: AsyncSession) -> list[ToolDefinition]:
        definitions: list[ToolDefinition] = []
        specs = list(TOOL_SPECS) + [
            ToolSpec(
                key,
                name,
                "Registered controlled capability; adapter is enabled in its delivery phase.",
                risk,
                external,
                reversible,
                True,
                Role.admin,
                {"type": "object"},
                {"type": "object"},
                enabled=False,
            )
            for key, name, risk, external, reversible in FUTURE_CONTROLLED_SPECS
        ]
        for spec in specs:
            definition = await session.scalar(
                select(ToolDefinition).where(
                    ToolDefinition.key == spec.key, ToolDefinition.version == 1
                )
            )
            if definition is None:
                definition = ToolDefinition(key=spec.key, version=1)
                session.add(definition)
            definition.name = spec.name
            definition.description = spec.description
            definition.risk_level = spec.risk_level
            definition.input_schema = spec.input_schema
            definition.output_schema = spec.output_schema
            definition.is_external = spec.is_external
            definition.is_reversible = spec.is_reversible
            definition.requires_approval_by_default = spec.requires_approval
            definition.enabled = spec.enabled
            definitions.append(definition)
        await session.flush()
        return definitions

    async def execute(
        self,
        session: AsyncSession,
        *,
        business_id: UUID,
        workflow_run_id: UUID,
        workflow_step_id: UUID,
        tool_key: str,
        payload: dict[str, Any],
        role: Role,
        user_id: str,
        idempotency_key: str,
        requested_permission: str = "execute",
    ) -> ToolCall:
        if requested_permission not in PERMISSION_RANK:
            raise ValueError("Unknown tool permission")
        run, step = await self._run_and_step(
            session, business_id, workflow_run_id, workflow_step_id
        )
        definition = await session.scalar(
            select(ToolDefinition).where(
                ToolDefinition.key == tool_key,
                ToolDefinition.enabled.is_(True),
            )
        )
        if definition is None:
            raise ValueError("Tool is unavailable")
        spec = _spec(tool_key)
        _validate_schema(payload, spec.input_schema, "tool input")
        if ROLE_RANK[role] < ROLE_RANK[spec.required_role]:
            raise PermissionError("Role is not permitted to use this tool")
        permission = await session.scalar(
            select(ToolPermission)
            .where(
                ToolPermission.business_id == business_id,
                ToolPermission.tool_definition_id == definition.id,
                ToolPermission.role == role.value,
                or_(
                    ToolPermission.workflow_definition_id == run.workflow_definition_id,
                    ToolPermission.workflow_definition_id.is_(None),
                ),
            )
            .order_by(ToolPermission.workflow_definition_id.desc().nullslast())
        )
        if permission is None or PERMISSION_RANK[permission.permission] < PERMISSION_RANK[
            requested_permission
        ]:
            raise PermissionError("Tenant tool permission is missing")
        _validate_constraints(payload, permission.constraints)

        existing = await session.scalar(
            select(ToolCall).where(
                ToolCall.business_id == business_id,
                ToolCall.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_hash != _request_hash(payload):
                raise ValueError("Idempotency key was already used for a different request")
            return existing

        call = ToolCall(
            business_id=business_id,
            workflow_run_id=run.id,
            workflow_step_id=step.id,
            tool_definition_id=definition.id,
            permission_snapshot={
                "permission_id": str(permission.id),
                "permission": permission.permission,
                "role": role.value,
                "constraints": permission.constraints,
            },
            request_payload_sanitized=_sanitize(payload),
            request_hash=_request_hash(payload),
            idempotency_key=idempotency_key,
            status="running",
            attempt_count=1,
            started_at=datetime.now(UTC),
        )
        session.add(call)
        await session.flush()
        try:
            async with asyncio.timeout(spec.timeout_seconds):
                if tool_key == "request_human_approval":
                    result = await self._request_approval(
                        session, business_id, payload, user_id, run, step, definition
                    )
                else:
                    handler = self._handlers.get(tool_key)
                    if handler is None:
                        raise ValueError("Tool adapter is not implemented")
                    result = await handler(session, business_id, payload, user_id)
            _validate_schema(result, spec.output_schema, "tool output")
            call.response_payload_sanitized = _sanitize(result)
            call.status = "completed"
            call.completed_at = datetime.now(UTC)
            session.add(
                AuditLog(
                    business_id=business_id,
                    actor_id=user_id,
                    action="tool_call.completed",
                    resource_type="tool_call",
                    resource_id=str(call.id),
                    details={"tool": tool_key, "workflow_run_id": str(run.id)},
                )
            )
        except Exception as exc:
            call.status = "failed"
            call.error_code = _failure_code(exc)
            call.error_message_sanitized = f"{exc.__class__.__name__}: {str(exc)[:500]}"
            call.completed_at = datetime.now(UTC)
            raise
        finally:
            await session.commit()
        return call

    async def _run_and_step(
        self, session: AsyncSession, business_id: UUID, run_id: UUID, step_id: UUID
    ) -> tuple[WorkflowRun, WorkflowStep]:
        run = await session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.id == run_id, WorkflowRun.business_id == business_id
            )
        )
        step = await session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.id == step_id,
                WorkflowStep.workflow_run_id == run_id,
                WorkflowStep.business_id == business_id,
            )
        )
        if run is None or step is None:
            raise ValueError("Workflow run or step was not found for this tenant")
        return run, step

    async def _read_business_profile(
        self, session: AsyncSession, business_id: UUID, _payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        profile = await session.scalar(
            select(BusinessProfile)
            .where(
                BusinessProfile.business_id == business_id,
                BusinessProfile.active.is_(True),
                BusinessProfile.approval_status == "approved",
            )
            .order_by(BusinessProfile.version.desc())
        )
        if profile is not None:
            return {
                "id": str(profile.id),
                "version": profile.version,
                "legal_name": profile.legal_name,
                "display_name": profile.display_name,
                "description": profile.description,
                "industry": profile.industry,
                "business_model": profile.business_model,
                "timezone": profile.timezone,
                "locations": profile.locations,
                "opening_hours": profile.opening_hours,
                "contact_channels": profile.contact_channels,
                "website": profile.website,
                "target_markets": profile.target_markets,
                "customer_types": profile.customer_types,
                "provenance": {
                    "source_type": profile.source_type,
                    "source_id": profile.source_id,
                    "authority_level": profile.authority_level,
                    "effective_from": profile.effective_from,
                    "expires_at": profile.expires_at,
                    "approval_status": profile.approval_status,
                },
            }
        return {
            "id": str(business.id),
            "name": business.name,
            "primary_email": business.primary_email,
            "timezone": business.timezone,
            "whatsapp_number": business.whatsapp_number,
        }

    async def _read_brand_policy(
        self, session: AsyncSession, business_id: UUID, _payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        policies = (
            await session.scalars(
                select(BusinessPolicy)
                .where(
                    BusinessPolicy.business_id == business_id,
                    BusinessPolicy.active.is_(True),
                    BusinessPolicy.approval_status == "approved",
                )
                .order_by(BusinessPolicy.category, BusinessPolicy.version.desc())
            )
        ).all()
        if policies:
            return {
                "policies": [
                    {
                        "id": str(item.id),
                        "key": item.policy_key,
                        "category": item.category,
                        "name": item.name,
                        "rules": item.rules,
                        "version": item.version,
                        "source_type": item.source_type,
                        "source_id": item.source_id,
                        "authority_level": item.authority_level,
                        "effective_from": item.effective_from,
                        "expires_at": item.expires_at,
                        "approval_status": item.approval_status,
                    }
                    for item in policies
                ]
            }
        policy = (business.settings or {}).get("ai_policy", {})
        return policy if isinstance(policy, dict) else {}

    async def _read_official_pricing(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        query = select(PriceCatalogItem).where(
            PriceCatalogItem.business_id == business_id,
            PriceCatalogItem.active.is_(True),
        )
        if payload.get("service"):
            query = query.where(PriceCatalogItem.service == str(payload["service"]))
        rows = (await session.scalars(query.limit(100))).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "service": row.service,
                    "label": row.label,
                    "amount_min": str(row.amount_min) if row.amount_min is not None else None,
                    "amount_max": str(row.amount_max) if row.amount_max is not None else None,
                    "currency": row.currency,
                    "approved_by": row.approved_by,
                }
                for row in rows
            ]
        }

    async def _read_crm_contact(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        contact = await session.scalar(
            select(Contact).where(
                Contact.id == _uuid(payload.get("id")), Contact.business_id == business_id
            )
        )
        if contact is None:
            raise ValueError("Contact not found")
        return {
            "id": str(contact.id),
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            "preferred_channel": contact.preferred_channel,
            "is_existing_client": contact.is_existing_client,
        }

    async def _read_recent_conversation(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        thread_id = _uuid(payload.get("id"))
        thread = await session.scalar(
            select(EmailThread).where(
                EmailThread.id == thread_id, EmailThread.business_id == business_id
            )
        )
        if thread is None:
            raise ValueError("Thread not found")
        rows = (
            await session.scalars(
                select(EmailMessage)
                .where(EmailMessage.thread_id == thread.id)
                .order_by(EmailMessage.sent_at.desc())
                .limit(10)
            )
        ).all()
        return {
            "thread_id": str(thread.id),
            "messages": [
                {
                    "direction": row.direction.value,
                    "body_text": row.body_text[:2000],
                    "sent_at": row.sent_at.isoformat(),
                }
                for row in reversed(rows)
            ],
        }

    async def _calculate_quotation(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        input_data = payload.get("input_data")
        if not isinstance(input_data, dict):
            raise ValueError("input_data must be an object")
        calculation, proposal, subtotal, total, deposit = calculate_quote(
            business=business,
            template_type=str(payload.get("template_type") or "custom"),
            input_data=input_data,
        )
        return {
            "calculation": calculation,
            "proposal": proposal,
            "subtotal": str(subtotal),
            "total": str(total),
            "deposit": str(deposit) if deposit is not None else None,
        }

    async def _create_crm_lead(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        contact_id = _optional_uuid(payload.get("contact_id"))
        thread_id = _optional_uuid(payload.get("thread_id"))
        if contact_id is not None and await session.scalar(
            select(Contact.id).where(Contact.id == contact_id, Contact.business_id == business_id)
        ) is None:
            raise ValueError("Contact not found")
        if thread_id is not None and await session.scalar(
            select(EmailThread.id).where(
                EmailThread.id == thread_id, EmailThread.business_id == business_id
            )
        ) is None:
            raise ValueError("Thread not found")
        lead = CRMLead(
            business_id=business_id,
            contact_id=contact_id,
            thread_id=thread_id,
            title=str(payload["title"])[:240],
            stage=LeadStage.new,
            source=LeadSource.manual,
            service=str(payload.get("service") or "")[:120] or None,
            currency="NGN",
            probability=0,
            lead_score=0,
            temperature=LeadTemperature.cold,
            qualification_summary="",
            qualification_reasons=[],
            notes=str(payload.get("notes") or ""),
            owner_id=user_id,
        )
        session.add(lead)
        await session.flush()
        return {"lead_id": str(lead.id), "stage": lead.stage.value}

    async def _update_crm_stage(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        lead = await session.scalar(
            select(CRMLead).where(
                CRMLead.id == _uuid(payload["id"]), CRMLead.business_id == business_id
            )
        )
        if lead is None:
            raise ValueError("Lead not found")
        old_stage = lead.stage
        lead.stage = LeadStage(str(payload["stage"]))
        lead.closed_at = (
            datetime.now(UTC) if lead.stage in {LeadStage.won, LeadStage.lost} else None
        )
        return {
            "lead_id": str(lead.id),
            "old_stage": old_stage.value,
            "stage": lead.stage.value,
        }

    async def _create_draft(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        thread_id = _uuid(payload["thread_id"])
        message_id = _uuid(payload["source_message_id"])
        thread = await session.scalar(
            select(EmailThread).where(
                EmailThread.id == thread_id, EmailThread.business_id == business_id
            )
        )
        message = await session.scalar(
            select(EmailMessage)
            .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
            .where(
                EmailMessage.id == message_id,
                EmailMessage.thread_id == thread_id,
                EmailThread.business_id == business_id,
            )
        )
        if thread is None or message is None:
            raise ValueError("Tenant conversation or source message not found")
        draft = EmailDraft(
            thread_id=thread.id,
            source_message_id=message.id,
            subject=str(payload["subject"])[:1000],
            body_text=str(payload["body_text"])[:20_000],
            draft_type=str(payload["draft_type"])[:40],
            status=DraftStatus.pending,
            auto_send_eligible=False,
            policy_reasons=["Created by controlled workflow tool; review required"],
        )
        session.add(draft)
        await session.flush()
        return {"draft_id": str(draft.id), "status": draft.status.value}

    async def _create_quotation_draft(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        lead_id = _optional_uuid(payload.get("lead_id"))
        contact_id = _optional_uuid(payload.get("contact_id"))
        if lead_id is not None and await session.scalar(
            select(CRMLead.id).where(CRMLead.id == lead_id, CRMLead.business_id == business_id)
        ) is None:
            raise ValueError("Lead not found")
        if contact_id is not None and await session.scalar(
            select(Contact.id).where(Contact.id == contact_id, Contact.business_id == business_id)
        ) is None:
            raise ValueError("Contact not found")
        calculated = await self._calculate_quotation(session, business_id, payload, _user)
        quote = Quote(
            business_id=business_id,
            lead_id=lead_id,
            contact_id=contact_id,
            title=str(payload["title"])[:240],
            template_type=QuoteTemplateType(str(payload["template_type"])),
            status=QuoteStatus.draft,
            currency=str(payload.get("currency") or "NGN").upper()[:3],
            subtotal=Decimal(calculated["subtotal"]),
            total=Decimal(calculated["total"]),
            deposit_required=(
                Decimal(calculated["deposit"]) if calculated["deposit"] is not None else None
            ),
            input_data=dict(payload["input_data"]),
            calculation=dict(calculated["calculation"]),
            proposal=dict(calculated["proposal"]),
            internal_notes="Created by controlled workflow tool",
        )
        session.add(quote)
        await session.flush()
        return {"quote_id": str(quote.id), "status": quote.status.value}

    async def _schedule_follow_up(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        lead = await session.scalar(
            select(CRMLead).where(
                CRMLead.id == _uuid(payload["lead_id"]), CRMLead.business_id == business_id
            )
        )
        if lead is None or lead.thread_id is None:
            raise ValueError("Open tenant lead with a conversation is required")
        if lead.stage in {LeadStage.won, LeadStage.lost}:
            raise ValueError("Closed leads cannot be scheduled")
        existing = (
            await session.scalars(
                select(FollowUpTask).where(
                    FollowUpTask.business_id == business_id,
                    FollowUpTask.lead_id == lead.id,
                    FollowUpTask.status == FollowUpStatus.scheduled,
                )
            )
        ).all()
        now = datetime.now(UTC)
        for task in existing:
            task.status = FollowUpStatus.cancelled
            task.completed_at = now
            task.error = "Replaced by a controlled workflow tool"
        cadence = str(payload["cadence"])
        tasks = [
            FollowUpTask(
                business_id=business_id,
                lead_id=lead.id,
                thread_id=lead.thread_id,
                contact_id=lead.contact_id,
                sequence_name=cadence,
                step_number=index,
                channel="email",
                status=FollowUpStatus.scheduled,
                scheduled_for=now + offset,
                subject="",
                body_text="",
                task_metadata={"created_by": user_id, "source": "tool_registry"},
            )
            for index, offset in enumerate(standard_follow_up_offsets(cadence), start=1)
        ]
        session.add_all(tasks)
        lead.next_follow_up_at = tasks[0].scheduled_for
        await session.flush()
        return {
            "lead_id": str(lead.id),
            "tasks_created": len(tasks),
            "cancelled_existing": len(existing),
            "task_ids": [str(task.id) for task in tasks],
        }

    async def _read_marketing_metrics(
        self, session: AsyncSession, business_id: UUID, payload: dict[str, Any], _user: str
    ) -> dict[str, Any]:
        query = select(MarketingMetric).where(MarketingMetric.business_id == business_id)
        if payload.get("source"):
            query = query.where(MarketingMetric.source == str(payload["source"]))
        rows = (
            await session.scalars(query.order_by(MarketingMetric.created_at.desc()).limit(100))
        ).all()
        return {
            "metrics": [
                {
                    "source": row.source,
                    "page_url": row.page_url,
                    "query": row.query,
                    "impressions": row.impressions,
                    "clicks": row.clicks,
                    "sessions": row.sessions,
                    "leads": row.leads,
                }
                for row in rows
            ]
        }

    async def _request_approval(
        self,
        session: AsyncSession,
        business_id: UUID,
        payload: dict[str, Any],
        _user_id: str,
        run: WorkflowRun,
        step: WorkflowStep,
        definition: ToolDefinition,
    ) -> dict[str, Any]:
        required = (
            "proposed_action_type",
            "proposed_action_payload",
            "reason",
            "risk_level",
            "required_role",
        )
        if any(not payload.get(key) for key in required):
            raise ValueError("Approval request is missing required information")
        proposed_tool = await session.scalar(
            select(ToolDefinition).where(
                ToolDefinition.key == str(payload["proposed_action_type"])
            )
        )
        approval = ApprovalRequest(
            business_id=business_id,
            workflow_run_id=run.id,
            workflow_step_id=step.id,
            proposed_action_type=str(payload["proposed_action_type"]),
            proposed_action_payload=dict(payload["proposed_action_payload"]),
            reason=str(payload["reason"]),
            decision_summary=str(payload.get("decision_summary") or ""),
            risk_level=str(payload["risk_level"]),
            requested_tool_id=(proposed_tool or definition).id,
            required_role=str(payload["required_role"]),
            original_payload=dict(payload["proposed_action_payload"]),
            final_payload=dict(payload["proposed_action_payload"]),
        )
        session.add(approval)
        run.status = "waiting_for_approval"
        step.status = "waiting_for_approval"
        await session.flush()
        return {"approval_request_id": str(approval.id), "status": approval.status}


def tool_spec(key: str) -> ToolSpec:
    for spec in TOOL_SPECS:
        if spec.key == key:
            return spec
    for item in FUTURE_CONTROLLED_SPECS:
        if item[0] == key:
            return ToolSpec(
                item[0],
                item[1],
                "Registered controlled capability; adapter is enabled in its delivery phase.",
                item[2],
                item[3],
                item[4],
                True,
                Role.admin,
                {"type": "object"},
                {"type": "object"},
                enabled=False,
            )
    raise ValueError("Unknown tool")


def _spec(key: str) -> ToolSpec:
    spec = tool_spec(key)
    if not spec.enabled:
        raise ValueError("Tool is unavailable")
    return spec


def _validate_schema(value: Any, schema: dict[str, Any], label: str) -> None:
    allowed = schema.get("enum")
    if isinstance(allowed, list) and value not in allowed:
        raise ValueError(f"{label} must be one of: {', '.join(map(str, allowed))}")
    expected = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float, Decimal)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }
    if expected in type_matches and not type_matches[expected]:
        raise ValueError(f"{label} must be {expected}")
    if not isinstance(value, dict) or expected != "object":
        return
    required = schema.get("required", [])
    missing = [key for key in required if key not in value]
    if missing:
        raise ValueError(f"{label} is missing required field(s): {', '.join(missing)}")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        unknown = sorted(set(value) - set(properties))
        if unknown:
            raise ValueError(f"{label} has unknown field(s): {', '.join(unknown)}")
    for key, field_schema in properties.items():
        if key in value and isinstance(field_schema, dict):
            _validate_schema(value[key], field_schema, f"{label}.{key}")


def _validate_constraints(payload: dict[str, Any], constraints: dict[str, Any]) -> None:
    required_equals = constraints.get("required_equals", {})
    if isinstance(required_equals, dict):
        for key, expected in required_equals.items():
            if payload.get(key) != expected:
                raise PermissionError(f"Tool permission requires {key}={expected}")
    allowed_values = constraints.get("allowed_values", {})
    if isinstance(allowed_values, dict):
        for key, values in allowed_values.items():
            if isinstance(values, list) and key in payload and payload[key] not in values:
                raise PermissionError(f"Tool permission does not allow this {key}")


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(part in str(key).lower() for part in ("token", "secret", "password", "key"))
                else _sanitize(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value[:100]]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value[:4000]
    return value


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid record id") from exc


def _optional_uuid(value: object) -> UUID | None:
    if value in (None, ""):
        return None
    return _uuid(value)


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, PermissionError):
        return "authorization"
    if isinstance(exc, ValueError):
        return "validation"
    if isinstance(exc, TimeoutError):
        return "transient_failure"
    return "permanent_failure"
