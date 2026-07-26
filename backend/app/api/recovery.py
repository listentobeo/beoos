from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.failures import RecoveryDecision
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    DurableJob,
    ExternalActionReconciliation,
    ToolCall,
)
from app.services.failure_recovery import RETRYABLE_FAILURES, recovery_message, retry_delay

router = APIRouter(prefix="/businesses/{business_id}/recovery", tags=["recovery"])


@router.get("")
async def recovery_queue(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    jobs = (
        await session.scalars(
            select(DurableJob)
            .where(
                DurableJob.business_id == business_id,
                DurableJob.status.in_(["dead_letter", "retry_scheduled"]),
            )
            .order_by(DurableJob.updated_at.desc())
        )
    ).all()
    tool_calls = (
        await session.scalars(
            select(ToolCall)
            .where(
                ToolCall.business_id == business_id,
                or_(
                    ToolCall.status == "failed",
                    ToolCall.reconciliation_status.in_(["required", "pending"]),
                ),
            )
            .order_by(ToolCall.updated_at.desc())
        )
    ).all()
    reconciliations = (
        await session.scalars(
            select(ExternalActionReconciliation)
            .where(
                ExternalActionReconciliation.business_id == business_id,
                ExternalActionReconciliation.status.in_(
                    ["pending", "investigating", "retry_scheduled"]
                ),
            )
            .order_by(ExternalActionReconciliation.updated_at.desc())
        )
    ).all()
    return {
        "durable_jobs": [_job_view(row) for row in jobs],
        "tool_calls": [_tool_view(row) for row in tool_calls],
        "reconciliations": [_reconciliation_view(row) for row in reconciliations],
    }


@router.post("/tool-calls/{tool_call_id}/reconciliation", status_code=201)
async def open_tool_reconciliation(
    business_id: UUID,
    tool_call_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    call = await session.scalar(
        select(ToolCall).where(
            ToolCall.id == tool_call_id,
            ToolCall.business_id == business_id,
        )
    )
    if call is None:
        raise HTTPException(status_code=404, detail="Tool call not found")
    category = call.failure_category or (
        "external_action_unknown" if call.external_state == "unknown" else "permanent_failure"
    )
    existing = await session.scalar(
        select(ExternalActionReconciliation).where(
            ExternalActionReconciliation.business_id == business_id,
            ExternalActionReconciliation.action_type == "tool_call",
            ExternalActionReconciliation.idempotency_key == call.idempotency_key,
        )
    )
    if existing:
        return _reconciliation_view(existing)
    row = ExternalActionReconciliation(
        business_id=business_id,
        workflow_run_id=call.workflow_run_id,
        tool_call_id=call.id,
        action_type="tool_call",
        idempotency_key=call.idempotency_key,
        request_hash=call.request_hash,
        failure_category=category,
        status="investigating" if category == "external_action_unknown" else "pending",
        provider_reference=call.external_reference,
        attempt_count=call.attempt_count,
        user_message=recovery_message(category),  # type: ignore[arg-type]
    )
    call.reconciliation_status = "pending"
    session.add(row)
    await session.flush()
    await _audit(session, business_id, access.user_id, "reconciliation.opened", row.id, {})
    await session.commit()
    return _reconciliation_view(row)


@router.post("/reconciliations/{reconciliation_id}/decision")
async def decide_reconciliation(
    business_id: UUID,
    reconciliation_id: UUID,
    payload: RecoveryDecision,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    row = await session.scalar(
        select(ExternalActionReconciliation).where(
            ExternalActionReconciliation.id == reconciliation_id,
            ExternalActionReconciliation.business_id == business_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    if row.status in {"reconciled", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Reconciliation is already closed")
    call = await session.get(ToolCall, row.tool_call_id) if row.tool_call_id else None
    job = await session.get(DurableJob, row.durable_job_id) if row.durable_job_id else None
    now = datetime.now(UTC)
    if payload.action == "retry":
        if row.failure_category == "external_action_unknown":
            raise HTTPException(
                status_code=409,
                detail="Unknown external state must be reconciled before retry",
            )
        if row.failure_category not in RETRYABLE_FAILURES:
            raise HTTPException(status_code=409, detail="Failure category is not retryable")
        delay = retry_delay(row.failure_category, row.attempt_count + 1)  # type: ignore[arg-type]
        row.status = "retry_scheduled"
        row.next_retry_at = now + delay if delay else now
        if job:
            job.status = "retry_scheduled"
            job.available_at = row.next_retry_at
        if call:
            call.status = "pending"
            call.reconciliation_status = "pending"
    elif payload.action == "mark_reconciled":
        row.status = "reconciled"
        row.resolved_by = access.user_id
        row.resolved_at = now
        row.provider_reference = payload.provider_reference or row.provider_reference
        if call:
            call.status = "completed"
            call.external_state = "confirmed"
            call.reconciliation_status = "reconciled"
    elif payload.action == "cancel":
        row.status = "cancelled"
        row.resolved_by = access.user_id
        row.resolved_at = now
        if job:
            job.status = "cancelled"
        if call and call.external_state != "confirmed":
            call.status = "cancelled"
            call.reconciliation_status = "cancelled"
    else:
        row.status = "failed"
        row.resolved_by = access.user_id
        row.resolved_at = now
        if call:
            call.status = "failed"
            call.reconciliation_status = "failed"
    row.resolution = {
        "action": payload.action,
        "reason": payload.reason,
        "provider_reference": payload.provider_reference,
    }
    await _audit(
        session,
        business_id,
        access.user_id,
        "reconciliation.decided",
        row.id,
        row.resolution,
    )
    await session.commit()
    return _reconciliation_view(row)


async def _audit(
    session: AsyncSession,
    business_id: UUID,
    actor_id: str,
    action: str,
    resource_id: UUID,
    details: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=actor_id,
            action=action,
            resource_type="external_action_reconciliation",
            resource_id=str(resource_id),
            details=details,
        )
    )


def _job_view(row: DurableJob) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "type": row.job_type,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "last_error": row.last_error,
        "available_at": row.available_at,
    }


def _tool_view(row: ToolCall) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "status": row.status,
        "failure_category": row.failure_category,
        "external_state": row.external_state,
        "reconciliation_status": row.reconciliation_status,
        "attempt_count": row.attempt_count,
        "error": row.error_message_sanitized,
    }


def _reconciliation_view(row: ExternalActionReconciliation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "action_type": row.action_type,
        "failure_category": row.failure_category,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "next_retry_at": row.next_retry_at,
        "provider_reference": row.provider_reference,
        "user_message": row.user_message,
        "resolution": row.resolution,
    }
