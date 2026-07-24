from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_business_access
from app.domain.traces import WorkflowTraceDetail, WorkflowTraceSummary
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AIExecution,
    ApprovalRequest,
    Contact,
    DurableJob,
    HumanCorrection,
    Outcome,
    ToolCall,
    ToolDefinition,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)

router = APIRouter(prefix="/businesses/{business_id}/traces", tags=["workflow-traces"])


@router.get("", response_model=list[WorkflowTraceSummary])
async def list_workflow_traces(
    business_id: UUID,
    workflow: str | None = None,
    run_status: str | None = Query(default=None, alias="status"),
    channel: str | None = None,
    customer: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    approval_state: str | None = None,
    outcome: str | None = None,
    model: str | None = None,
    failure_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[WorkflowTraceSummary]:
    query = (
        select(WorkflowRun, WorkflowDefinition)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowRun.workflow_definition_id)
        .where(WorkflowRun.business_id == business_id)
        .order_by(WorkflowRun.created_at.desc())
        .limit(limit)
    )
    if workflow:
        query = query.where(WorkflowDefinition.key == workflow)
    if run_status:
        query = query.where(WorkflowRun.status == run_status)
    if channel:
        query = query.where(WorkflowRun.trigger_type == channel)
    if customer:
        query = query.where(
            cast(WorkflowRun.run_metadata["contact_id"].astext, String) == str(customer)
        )
    if date_from:
        query = query.where(WorkflowRun.created_at >= date_from)
    if date_to:
        query = query.where(WorkflowRun.created_at <= date_to)
    if approval_state:
        query = query.where(
            exists(
                select(ApprovalRequest.id).where(
                    ApprovalRequest.workflow_run_id == WorkflowRun.id,
                    ApprovalRequest.business_id == business_id,
                    ApprovalRequest.status == approval_state,
                )
            )
        )
    if outcome:
        query = query.where(
            exists(
                select(Outcome.id).where(
                    Outcome.workflow_run_id == WorkflowRun.id,
                    Outcome.business_id == business_id,
                    Outcome.outcome_type == outcome,
                )
            )
        )
    if model:
        query = query.where(
            exists(
                select(AIExecution.id).where(
                    AIExecution.workflow_run_id == WorkflowRun.id,
                    AIExecution.business_id == business_id,
                    AIExecution.model == model,
                )
            )
        )
    if failure_type:
        query = query.where(
            (WorkflowRun.last_error_code == failure_type)
            | exists(
                select(WorkflowStep.id).where(
                    WorkflowStep.workflow_run_id == WorkflowRun.id,
                    WorkflowStep.error_code == failure_type,
                )
            )
        )
    rows = (await session.execute(query)).all()
    summaries: list[WorkflowTraceSummary] = []
    for run, definition in rows:
        contact = await _contact(session, business_id, run.run_metadata.get("contact_id"))
        approval = await session.scalar(
            select(ApprovalRequest)
            .where(ApprovalRequest.workflow_run_id == run.id)
            .order_by(ApprovalRequest.created_at.desc())
        )
        outcomes = (
            await session.scalars(
                select(Outcome).where(Outcome.workflow_run_id == run.id)
            )
        ).all()
        ai = await session.scalar(
            select(AIExecution)
            .where(AIExecution.workflow_run_id == run.id)
            .order_by(AIExecution.created_at.desc())
        )
        failure = run.last_error_code or await session.scalar(
            select(WorkflowStep.error_code)
            .where(
                WorkflowStep.workflow_run_id == run.id,
                WorkflowStep.error_code.is_not(None),
            )
            .limit(1)
        )
        summaries.append(
            WorkflowTraceSummary(
                run_id=run.id,
                workflow_key=definition.key,
                workflow_name=definition.name,
                workflow_version=run.workflow_version,
                status=run.status,
                channel=run.trigger_type,
                customer_id=contact.id if contact else None,
                customer_name=contact.name if contact else None,
                approval_state=approval.status if approval else None,
                outcome_types=sorted({item.outcome_type for item in outcomes}),
                model=ai.model if ai else None,
                failure_type=failure,
                started_at=run.started_at,
                completed_at=run.completed_at,
                created_at=run.created_at,
            )
        )
    return summaries


@router.get("/{run_id}", response_model=WorkflowTraceDetail)
async def get_workflow_trace(
    business_id: UUID,
    run_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> WorkflowTraceDetail:
    row = (
        await session.execute(
            select(WorkflowRun, WorkflowDefinition)
            .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowRun.workflow_definition_id)
            .where(WorkflowRun.id == run_id, WorkflowRun.business_id == business_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow trace not found")
    run, definition = row
    steps = (
        await session.scalars(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run.id)
            .order_by(WorkflowStep.sequence)
        )
    ).all()
    ai_executions = (
        await session.scalars(
            select(AIExecution)
            .where(AIExecution.workflow_run_id == run.id)
            .order_by(AIExecution.created_at)
        )
    ).all()
    tool_rows = (
        await session.execute(
            select(ToolCall, ToolDefinition)
            .join(ToolDefinition, ToolDefinition.id == ToolCall.tool_definition_id)
            .where(ToolCall.workflow_run_id == run.id)
            .order_by(ToolCall.created_at)
        )
    ).all()
    tool_pairs = [(row[0], row[1]) for row in tool_rows]
    approvals = (
        await session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.workflow_run_id == run.id)
            .order_by(ApprovalRequest.created_at)
        )
    ).all()
    corrections = (
        await session.scalars(
            select(HumanCorrection)
            .where(HumanCorrection.workflow_run_id == run.id)
            .order_by(HumanCorrection.created_at)
        )
    ).all()
    outcomes = (
        await session.scalars(
            select(Outcome)
            .where(Outcome.workflow_run_id == run.id)
            .order_by(Outcome.observed_at)
        )
    ).all()
    jobs = (
        await session.scalars(
            select(DurableJob)
            .where(DurableJob.workflow_run_id == run.id)
            .order_by(DurableJob.created_at)
        )
    ).all()
    contact = await _contact(session, business_id, run.run_metadata.get("contact_id"))
    latest_ai = ai_executions[-1] if ai_executions else None
    ai_output = latest_ai.structured_output if latest_ai else {}
    policy_steps = [item for item in steps if item.step_type == "policy"]
    deterministic_steps = [item for item in steps if item.step_type == "deterministic"]
    context_sources = _unique_context_sources(ai_executions)
    cost = sum((item.estimated_cost or Decimal("0") for item in ai_executions), Decimal("0"))
    latency = sum(item.latency_ms or 0 for item in ai_executions)

    return WorkflowTraceDetail(
        run_id=run.id,
        trigger={
            "type": run.trigger_type,
            "reference_type": run.trigger_reference_type,
            "reference_id": run.trigger_reference_id,
            "correlation_id": run.correlation_id,
            "idempotency_key": run.idempotency_key,
            "created_at": run.created_at,
        },
        customer_and_channel={
            "channel": run.trigger_type,
            "customer": (
                {
                    "id": str(contact.id),
                    "name": contact.name,
                    "email": contact.email,
                    "phone": contact.phone,
                }
                if contact
                else None
            ),
        },
        workflow={
            "definition_id": str(definition.id),
            "key": definition.key,
            "name": definition.name,
            "version": run.workflow_version,
            "deployment_mode": definition.deployment_mode,
            "status": run.status,
        },
        business_context_sources=context_sources,
        extracted_information=(
            ai_output.get("extracted_fields", {})
            if isinstance(ai_output.get("extracted_fields"), dict)
            else {}
        ),
        missing_information=_list_of_strings(ai_output.get("missing_information")),
        ai_operational_summary=str(ai_output.get("operational_summary") or ""),
        policy_checks=(
            policy_steps[-1].output_snapshot.get("policy_result", {})
            if policy_steps
            else {}
        ),
        deterministic_calculations=[
            {
                "step_key": item.step_key,
                "output": item.output_snapshot,
                "completed_at": item.completed_at,
            }
            for item in deterministic_steps
        ],
        tool_calls=[
            {
                "id": str(call.id),
                "tool": tool.key,
                "status": call.status,
                "permission": call.permission_snapshot,
                "request": call.request_payload_sanitized,
                "response": call.response_payload_sanitized,
                "external_reference": call.external_reference,
                "attempt_count": call.attempt_count,
                "started_at": call.started_at,
                "completed_at": call.completed_at,
                "error_code": call.error_code,
                "error_message": call.error_message_sanitized,
            }
            for call, tool in tool_pairs
        ],
        approval_decisions=[
            {
                "id": str(item.id),
                "proposed_action": item.proposed_action_type,
                "reason": item.reason,
                "risk": item.risk_level,
                "status": item.status,
                "decided_by": item.decided_by,
                "decision_reason": item.decision_reason,
                "decided_at": item.decided_at,
                "execution_status": item.execution_status,
                "execution_reference": item.execution_reference,
            }
            for item in approvals
        ],
        human_edits=[
            {
                "id": str(item.id),
                "type": item.correction_type,
                "original": item.original_value,
                "corrected": item.corrected_value,
                "changed_fields": item.changed_fields,
                "reason": item.reason,
                "corrected_by": item.corrected_by,
                "final_action": item.final_action,
                "result": item.result,
                "created_at": item.created_at,
            }
            for item in corrections
        ],
        external_actions=[
            {
                "tool": tool.key,
                "status": call.status,
                "external_reference": call.external_reference,
                "completed_at": call.completed_at,
            }
            for call, tool in tool_pairs
            if tool.is_external
        ],
        result={
            "status": run.status,
            "completed_at": run.completed_at,
            "last_error_code": run.last_error_code,
            "last_error_message": run.last_error_message_sanitized,
        },
        outcomes=[
            {
                "id": str(item.id),
                "type": item.outcome_type,
                "status": item.status,
                "value_numeric": (
                    str(item.value_numeric) if item.value_numeric is not None else None
                ),
                "value_currency": item.value_currency,
                "value_text": item.value_text,
                "source": item.source,
                "observed_at": item.observed_at,
                "confidence": str(item.confidence) if item.confidence is not None else None,
            }
            for item in outcomes
        ],
        estimated_cost=cost,
        latency_ms=latency,
        retry_history=[
            {
                "job_id": str(item.id),
                "job_type": item.job_type,
                "status": item.status,
                "attempt_count": item.attempt_count,
                "max_attempts": item.max_attempts,
                "last_error": item.last_error,
                "available_at": item.available_at,
                "completed_at": item.completed_at,
            }
            for item in jobs
        ],
        errors_and_recovery=_errors(run, steps, tool_pairs, jobs),
        steps=[
            {
                "id": str(item.id),
                "sequence": item.sequence,
                "key": item.step_key,
                "type": item.step_type,
                "status": item.status,
                "started_at": item.started_at,
                "completed_at": item.completed_at,
                "retry_count": item.retry_count,
                "error_code": item.error_code,
                "error_message": item.error_message_sanitized,
            }
            for item in steps
        ],
    )


async def _contact(
    session: AsyncSession, business_id: UUID, contact_id: object
) -> Contact | None:
    if not contact_id:
        return None
    try:
        parsed = UUID(str(contact_id))
    except ValueError:
        return None
    result = await session.scalars(
        select(Contact).where(Contact.id == parsed, Contact.business_id == business_id)
    )
    return result.one_or_none()


def _unique_context_sources(
    executions: Sequence[AIExecution],
) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for execution in executions:
        for item in execution.context_references:
            source_type = str(item.get("source_type") or "")
            source_id = str(item.get("source_id") or "")
            found[(source_type, source_id)] = item
    return list(found.values())


def _list_of_strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _errors(
    run: WorkflowRun,
    steps: Sequence[WorkflowStep],
    tools: Sequence[tuple[ToolCall, ToolDefinition]],
    jobs: Sequence[DurableJob],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if run.last_error_code:
        errors.append(
            {
                "source": "workflow_run",
                "code": run.last_error_code,
                "message": run.last_error_message_sanitized,
                "recovery": run.status,
            }
        )
    errors.extend(
        {
            "source": "workflow_step",
            "step": item.step_key,
            "code": item.error_code,
            "message": item.error_message_sanitized,
            "recovery": f"retry_count={item.retry_count}",
        }
        for item in steps
        if item.error_code
    )
    errors.extend(
        {
            "source": "tool_call",
            "tool": definition.key,
            "code": call.error_code,
            "message": call.error_message_sanitized,
            "recovery": call.status,
        }
        for call, definition in tools
        if call.error_code
    )
    errors.extend(
        {
            "source": "durable_job",
            "job_type": item.job_type,
            "code": "job_failure",
            "message": item.last_error,
            "recovery": item.status,
        }
        for item in jobs
        if item.last_error
    )
    return errors
