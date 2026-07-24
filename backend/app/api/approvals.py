from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_business_access
from app.domain.approvals import ApprovalDecisionInput, ApprovalView
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    ApprovalRequest,
    AuditLog,
    Business,
    BusinessStaffAuthority,
    Contact,
    EmailDraft,
    HumanCorrection,
    Outcome,
    Role,
    ToolCall,
    ToolDefinition,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)
from app.services.tool_registry import ROLE_RANK, ToolRegistry

router = APIRouter(prefix="/businesses/{business_id}/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalView])
async def list_approvals(
    business_id: UUID,
    approval_status: str | None = Query(default="pending", alias="status"),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalView]:
    query = (
        select(
            ApprovalRequest,
            Business,
            WorkflowRun,
            WorkflowDefinition,
            Contact,
            ToolDefinition,
        )
        .join(Business, Business.id == ApprovalRequest.business_id)
        .join(WorkflowRun, WorkflowRun.id == ApprovalRequest.workflow_run_id)
        .join(
            WorkflowDefinition,
            WorkflowDefinition.id == WorkflowRun.workflow_definition_id,
        )
        .outerjoin(Contact, Contact.id == ApprovalRequest.affected_customer_id)
        .outerjoin(ToolDefinition, ToolDefinition.id == ApprovalRequest.requested_tool_id)
        .where(ApprovalRequest.business_id == business_id)
        .order_by(ApprovalRequest.created_at.asc())
    )
    if approval_status:
        query = query.where(ApprovalRequest.status == approval_status)
    rows = (await session.execute(query)).all()
    return [
        _view(approval, business, run, workflow, customer, tool)
        for approval, business, run, workflow, customer, tool in rows
    ]


@router.post("/{approval_id}/decide", response_model=ApprovalView)
async def decide_approval(
    business_id: UUID,
    approval_id: UUID,
    payload: ApprovalDecisionInput,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> ApprovalView:
    approval = await session.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.business_id == business_id,
        )
        .with_for_update()
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Approval request is already decided")
    if approval.expires_at is not None and approval.expires_at <= datetime.now(UTC):
        approval.status = "expired"
        await session.commit()
        raise HTTPException(status_code=409, detail="Approval request has expired")
    run = await session.get(WorkflowRun, approval.workflow_run_id)
    if run is None or run.business_id != business_id:
        raise HTTPException(status_code=409, detail="Workflow run is unavailable")
    workflow = await session.get(WorkflowDefinition, run.workflow_definition_id)
    await _authorize_decision(session, access, approval, workflow)

    final_payload = approval.proposed_action_payload
    if payload.action == "edit_and_approve":
        if payload.edited_payload is None or payload.correction_reason is None:
            raise HTTPException(
                status_code=400,
                detail="Edited approval requires payload and structured correction reason",
            )
        final_payload = payload.edited_payload
    elif payload.edited_payload is not None:
        raise HTTPException(status_code=400, detail="Edits are only valid with edit_and_approve")

    now = datetime.now(UTC)
    approval.decided_by = access.user_id
    approval.decision_reason = payload.decision_reason
    approval.decided_at = now
    approval.final_payload = final_payload
    approval.status = _decision_status(payload.action)
    changed_fields = _changed_fields(approval.proposed_action_payload, final_payload)
    correction: HumanCorrection | None = None
    if payload.action == "edit_and_approve":
        correction = HumanCorrection(
            business_id=business_id,
            workflow_run_id=run.id,
            approval_request_id=approval.id,
            correction_type=str(payload.correction_reason),
            original_value=approval.original_payload,
            corrected_value=final_payload,
            changed_fields=changed_fields,
            reason=payload.decision_reason,
            corrected_by=access.user_id,
            final_action=payload.action,
            result={"status": "pending_execution"},
            approved_for_dataset=False,
        )
        session.add(correction)

    if payload.action in {"approve", "edit_and_approve"}:
        already = await _already_executed(session, approval, final_payload)
        if already:
            approval.execution_status = "already_executed"
            approval.execution_reference = already
            run.status = "completed"
            run.completed_at = now
        else:
            approval.execution_status = "approved_pending_execution"
    elif payload.action == "request_more_information":
        run.status = "waiting_for_information"
    elif payload.action == "escalate":
        run.status = "escalated"
    else:
        run.status = "cancelled" if payload.action == "cancel" else "rejected"
        run.completed_at = now

    session.add(
        Outcome(
            business_id=business_id,
            workflow_run_id=run.id,
            outcome_type="approval_decision",
            status=approval.status,
            value_text=payload.action,
            source="human_approval",
            recorded_by=access.user_id,
            observed_at=now,
            confidence=None,
            outcome_metadata={"approval_request_id": str(approval.id)},
        )
    )
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action=f"approval.{payload.action}",
            resource_type="approval_request",
            resource_id=str(approval.id),
            details={
                "workflow_run_id": str(run.id),
                "changed_fields": changed_fields,
                "execution_status": approval.execution_status,
            },
        )
    )
    await session.commit()

    if (
        payload.action in {"approve", "edit_and_approve"}
        and approval.execution_status == "approved_pending_execution"
    ):
        await _execute_approved_action(
            session, approval, run, final_payload, access, correction
        )

    business = await session.get(Business, business_id)
    customer = (
        await session.get(Contact, approval.affected_customer_id)
        if approval.affected_customer_id
        else None
    )
    tool = (
        await session.get(ToolDefinition, approval.requested_tool_id)
        if approval.requested_tool_id
        else None
    )
    assert business is not None
    assert workflow is not None
    return _view(approval, business, run, workflow, customer, tool)


async def _authorize_decision(
    session: AsyncSession,
    access: BusinessAccess,
    approval: ApprovalRequest,
    workflow: WorkflowDefinition | None,
) -> None:
    if access.role == Role.viewer:
        raise HTTPException(status_code=403, detail="Viewer cannot decide approvals")
    required = Role(approval.required_role)
    if ROLE_RANK[access.role] < ROLE_RANK[required]:
        raise HTTPException(status_code=403, detail="Approval role is insufficient")
    if access.role in {Role.owner, Role.admin}:
        return
    authority = await session.scalar(
        select(BusinessStaffAuthority).where(
            BusinessStaffAuthority.business_id == access.business_id,
            BusinessStaffAuthority.clerk_user_id == access.user_id,
            BusinessStaffAuthority.approval_status == "approved",
        )
    )
    scopes = set(authority.approval_authority if authority else [])
    allowed = {
        "*",
        approval.proposed_action_type,
        f"workflow:{workflow.key}" if workflow else "",
    }
    if authority is None or not scopes.intersection(allowed):
        raise HTTPException(status_code=403, detail="Workflow-specific approval authority missing")
    if (
        approval.financial_impact is not None
        and authority.financial_limit is not None
        and approval.financial_impact > authority.financial_limit
    ):
        raise HTTPException(status_code=403, detail="Approval exceeds financial authority")


async def _execute_approved_action(
    session: AsyncSession,
    approval: ApprovalRequest,
    run: WorkflowRun,
    final_payload: dict[str, Any],
    access: BusinessAccess,
    correction: HumanCorrection | None,
) -> None:
    step = await session.get(WorkflowStep, approval.workflow_step_id)
    tool = (
        await session.get(ToolDefinition, approval.requested_tool_id)
        if approval.requested_tool_id
        else None
    )
    if step is None or tool is None:
        approval.execution_status = "failed"
        approval.execution_reference = "missing_workflow_step_or_tool"
        run.status = "failed"
        await session.commit()
        return
    try:
        call = await ToolRegistry().execute(
            session,
            business_id=approval.business_id,
            workflow_run_id=run.id,
            workflow_step_id=step.id,
            tool_key=tool.key,
            payload=final_payload,
            role=access.role,
            user_id=access.user_id,
            idempotency_key=f"approval:{approval.id}",
            requested_permission="execute",
        )
        approval.execution_status = call.status
        approval.execution_reference = str(call.id)
        run.status = "completed" if call.status == "completed" else "failed"
        run.completed_at = datetime.now(UTC) if run.status == "completed" else None
        if correction is not None:
            correction.result = {
                "status": call.status,
                "tool_call_id": str(call.id),
            }
    except Exception as exc:
        approval.execution_status = "failed"
        approval.execution_reference = f"{exc.__class__.__name__}: {str(exc)[:300]}"
        run.status = "failed"
        if correction is not None:
            correction.result = {
                "status": "failed",
                "error_type": exc.__class__.__name__,
            }
    await session.commit()


async def _already_executed(
    session: AsyncSession,
    approval: ApprovalRequest,
    payload: dict[str, Any],
) -> str | None:
    if approval.execution_reference:
        return approval.execution_reference
    call = await session.scalar(
        select(ToolCall).where(
            ToolCall.business_id == approval.business_id,
            ToolCall.idempotency_key == f"approval:{approval.id}",
            ToolCall.status == "completed",
        )
    )
    if call is not None:
        return str(call.id)
    if approval.proposed_action_type == "create_draft":
        source_id = payload.get("source_message_id")
        if source_id:
            draft = await session.scalar(
                select(EmailDraft).where(EmailDraft.source_message_id == UUID(str(source_id)))
            )
            if draft is not None:
                return str(draft.id)
    return None


def _decision_status(action: str) -> str:
    return {
        "approve": "approved",
        "edit_and_approve": "approved",
        "reject": "rejected",
        "request_more_information": "more_information_requested",
        "escalate": "escalated",
        "cancel": "cancelled",
    }[action]


def _changed_fields(original: dict[str, Any], edited: dict[str, Any]) -> list[str]:
    return sorted(
        key
        for key in set(original) | set(edited)
        if original.get(key) != edited.get(key)
    )


def _view(
    approval: ApprovalRequest,
    business: Business,
    run: WorkflowRun,
    workflow: WorkflowDefinition,
    customer: Contact | None,
    tool: ToolDefinition | None,
) -> ApprovalView:
    policy = approval.original_payload.get("policy_result", {})
    return ApprovalView(
        id=approval.id,
        business_id=business.id,
        business_name=business.name,
        customer=(
            {
                "id": str(customer.id),
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
            }
            if customer
            else None
        ),
        workflow={
            "id": str(workflow.id),
            "run_id": str(run.id),
            "key": workflow.key,
            "name": workflow.name,
            "version": run.workflow_version,
            "status": run.status,
        },
        proposed_action={
            "type": approval.proposed_action_type,
            "payload": approval.proposed_action_payload,
        },
        ai_summary=approval.decision_summary,
        confidence=approval.confidence,
        risk=approval.risk_level,
        policy_checks=policy if isinstance(policy, dict) else {},
        context_sources=approval.context_references,
        financial_impact=approval.financial_impact,
        expires_at=approval.expires_at,
        tool=(
            {
                "id": str(tool.id),
                "key": tool.key,
                "name": tool.name,
                "risk_level": tool.risk_level,
            }
            if tool
            else None
        ),
        required_role=approval.required_role,
        status=approval.status,
        original_payload=approval.original_payload,
        final_payload=approval.final_payload,
        execution_status=approval.execution_status,
        execution_reference=approval.execution_reference,
        created_at=approval.created_at,
    )
