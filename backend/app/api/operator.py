from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_business_access
from app.domain.operator import (
    OperatorApprovalProposal,
    OperatorChatRequest,
    OperatorChatResponse,
    OperatorWorkflowStart,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    ApprovalRequest,
    AuditLog,
    Business,
    Contact,
    EmailMessage,
    EmailThread,
    Role,
    ToolDefinition,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)
from app.services.beo_enquiry_workflow import (
    WORKFLOW_KEY as COMMISSION_WORKFLOW_KEY,
)
from app.services.beo_enquiry_workflow import (
    record_commission_enquiry_workflow,
)
from app.services.operator import OperatorService

router = APIRouter(prefix="/businesses/{business_id}/operator", tags=["operator"])


@router.post("/chat", response_model=OperatorChatResponse)
async def operator_chat(
    business_id: UUID,
    payload: OperatorChatRequest,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> OperatorChatResponse:
    service = OperatorService(settings)
    return await service.chat(
        session=session,
        business_id=business_id,
        user_id=access.user_id,
        role=access.role,
        message=payload.message,
        mode=payload.mode,
        conversation_context=payload.conversation_context,
        conversation_id=payload.conversation_id,
    )


@router.post("/actions/start-workflow", status_code=202)
async def operator_start_workflow(
    business_id: UUID,
    payload: OperatorWorkflowStart,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if access.role == Role.viewer:
        raise HTTPException(status_code=403, detail="Viewer cannot start workflows")
    definition = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == payload.workflow_definition_id,
            or_(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.business_id.is_(None),
            ),
            WorkflowDefinition.status == "active",
            WorkflowDefinition.deployment_mode.in_(
                ["shadow", "approval_required", "limited_autonomy", "active"]
            ),
        )
    )
    if definition is None:
        raise HTTPException(
            status_code=409,
            detail="Only evaluated active tenant-compatible workflows can be started",
        )
    if (
        definition.key == COMMISSION_WORKFLOW_KEY
        and payload.trigger_reference_type == "email_message"
    ):
        try:
            message_id = UUID(payload.trigger_reference_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Email message reference must be a UUID"
            ) from exc
        message = await session.get(EmailMessage, message_id)
        thread = (
            await session.scalar(
                select(EmailThread).where(
                    EmailThread.id == message.thread_id,
                    EmailThread.business_id == business_id,
                )
            )
            if message
            else None
        )
        contact = (
            await session.scalar(
                select(Contact).where(
                    Contact.id == thread.contact_id,
                    Contact.business_id == business_id,
                )
            )
            if thread and thread.contact_id
            else None
        )
        business = await session.get(Business, business_id)
        channel = str(payload.metadata.get("channel", "manual"))
        allowed_channels = {"website_form", "gmail", "zoho", "whatsapp", "manual"}
        if message is None or thread is None or business is None or channel not in allowed_channels:
            raise HTTPException(
                status_code=422,
                detail="A tenant message, thread, business, and supported channel are required",
            )
        expected_key = f"{channel}:{message.id}"
        if payload.idempotency_key != expected_key:
            raise HTTPException(
                status_code=422,
                detail=f"Commission workflow idempotency key must be {expected_key}",
            )
        run = await record_commission_enquiry_workflow(
            session,
            settings,
            business=business,
            contact=contact,
            thread=thread,
            message=message,
            channel=cast(
                Literal["website_form", "gmail", "zoho", "whatsapp", "manual"],
                channel,
            ),
        )
        session.add(
            AuditLog(
                business_id=business_id,
                actor_id=access.user_id,
                action="operator.workflow_started",
                resource_type="workflow_run",
                resource_id=str(run.id),
                details={
                    "workflow_key": definition.key,
                    "execution": "reference_workflow_service",
                    "external_actions_controlled_by_deployment": True,
                },
            )
        )
        await session.commit()
        return {"id": str(run.id), "status": run.status}
    existing = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.business_id == business_id,
            WorkflowRun.workflow_definition_id == definition.id,
            WorkflowRun.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        return {"id": str(existing.id), "status": existing.status}
    run = WorkflowRun(
        business_id=business_id,
        workflow_definition_id=definition.id,
        workflow_version=definition.version,
        trigger_type=definition.trigger_type,
        trigger_reference_type=payload.trigger_reference_type,
        trigger_reference_id=payload.trigger_reference_id,
        correlation_id=payload.correlation_id,
        idempotency_key=payload.idempotency_key,
        status="queued",
        run_metadata={
            **payload.metadata,
            "source": "beoos_operator",
            "deployment_mode": definition.deployment_mode,
            "external_actions_executed": 0,
        },
        initiated_by_user_id=access.user_id,
    )
    session.add(run)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="operator.workflow_started",
            resource_type="workflow_run",
            resource_id=str(run.id),
            details={"workflow_key": definition.key, "external_actions_executed": 0},
        )
    )
    await session.commit()
    return {"id": str(run.id), "status": run.status}


@router.post("/actions/request-approval", status_code=201)
async def operator_request_approval(
    business_id: UUID,
    payload: OperatorApprovalProposal,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if access.role == Role.viewer:
        raise HTTPException(status_code=403, detail="Viewer cannot propose actions")
    run = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == payload.workflow_run_id,
            WorkflowRun.business_id == business_id,
        )
    )
    step = await session.scalar(
        select(WorkflowStep).where(
            WorkflowStep.id == payload.workflow_step_id,
            WorkflowStep.workflow_run_id == payload.workflow_run_id,
            WorkflowStep.business_id == business_id,
        )
    )
    if run is None or step is None:
        raise HTTPException(status_code=404, detail="Tenant workflow run or step not found")
    tool = (
        await session.scalar(
            select(ToolDefinition).where(
                ToolDefinition.id == payload.requested_tool_id,
                ToolDefinition.enabled.is_(True),
            )
        )
        if payload.requested_tool_id
        else None
    )
    if payload.requested_tool_id and tool is None:
        raise HTTPException(status_code=404, detail="Requested registered tool not found")
    approval = ApprovalRequest(
        business_id=business_id,
        workflow_run_id=run.id,
        workflow_step_id=step.id,
        proposed_action_type=payload.proposed_action_type,
        proposed_action_payload=payload.proposed_action_payload,
        reason=payload.reason,
        decision_summary=payload.decision_summary,
        context_references=[{"source": "operator_proposal", "workflow_run_id": str(run.id)}],
        risk_level=payload.risk_level,
        requested_tool_id=tool.id if tool else None,
        required_role=payload.required_role,
        status="pending",
        original_payload=payload.proposed_action_payload,
        final_payload=payload.proposed_action_payload,
    )
    session.add(approval)
    run.status = "waiting_for_approval"
    step.status = "waiting_for_approval"
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="operator.approval_requested",
            resource_type="approval_request",
            resource_id=str(approval.id),
            details={
                "proposed_action_type": approval.proposed_action_type,
                "external_action_executed": False,
                "requested_at": datetime.now(UTC).isoformat(),
            },
        )
    )
    await session.commit()
    return {"id": str(approval.id), "status": approval.status}
