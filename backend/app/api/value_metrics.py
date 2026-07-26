from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.value_metrics import WorkflowBaselineUpsert
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AIExecution,
    ApprovalRequest,
    AuditLog,
    HumanCorrection,
    Outcome,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowValueBaseline,
)
from app.services.value_metrics import median_minutes, metric, ratio

router = APIRouter(prefix="/businesses/{business_id}/value", tags=["business-value"])


@router.put("/baseline")
async def upsert_workflow_baseline(
    business_id: UUID,
    payload: WorkflowBaselineUpsert,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    baseline = await session.scalar(
        select(WorkflowValueBaseline).where(
            WorkflowValueBaseline.business_id == business_id,
            WorkflowValueBaseline.workflow_key == payload.workflow_key,
        )
    )
    values = payload.model_dump(exclude={"workflow_key"})
    if baseline is None:
        baseline = WorkflowValueBaseline(
            business_id=business_id,
            workflow_key=payload.workflow_key,
            recorded_by=access.user_id,
            source="user_estimate",
            **values,
        )
        session.add(baseline)
    else:
        for key, value in values.items():
            setattr(baseline, key, value)
        baseline.recorded_by = access.user_id
        baseline.source = "user_estimate"
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="workflow_value_baseline.updated",
            resource_type="workflow_value_baseline",
            resource_id=str(baseline.id),
            details={"workflow_key": payload.workflow_key, "source": "user_estimate"},
        )
    )
    await session.commit()
    return _baseline_view(baseline)


@router.get("/dashboard")
async def workflow_value_dashboard(
    business_id: UUID,
    workflow_key: str = "beo_art_commission_enquiry_v1",
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    definitions = select(WorkflowDefinition.id).where(
        WorkflowDefinition.key == workflow_key,
        (
            (WorkflowDefinition.business_id == business_id)
            | (WorkflowDefinition.business_id.is_(None))
        ),
    )
    runs = (
        await session.scalars(
            select(WorkflowRun).where(
                WorkflowRun.business_id == business_id,
                WorkflowRun.workflow_definition_id.in_(definitions),
            )
        )
    ).all()
    run_ids = [row.id for row in runs]
    baseline = await session.scalar(
        select(WorkflowValueBaseline).where(
            WorkflowValueBaseline.business_id == business_id,
            WorkflowValueBaseline.workflow_key == workflow_key,
        )
    )
    if not run_ids:
        return _empty_dashboard(business_id, workflow_key, baseline)
    approvals = (
        await session.scalars(
            select(ApprovalRequest).where(
                ApprovalRequest.business_id == business_id,
                ApprovalRequest.workflow_run_id.in_(run_ids),
            )
        )
    ).all()
    corrections = int(
        await session.scalar(
            select(func.count(HumanCorrection.id)).where(
                HumanCorrection.business_id == business_id,
                HumanCorrection.workflow_run_id.in_(run_ids),
            )
        )
        or 0
    )
    outcomes = (
        await session.scalars(
            select(Outcome).where(
                Outcome.business_id == business_id,
                Outcome.workflow_run_id.in_(run_ids),
            )
        )
    ).all()
    ai_cost = Decimal(
        await session.scalar(
            select(func.coalesce(func.sum(AIExecution.estimated_cost), 0)).where(
                AIExecution.business_id == business_id,
                AIExecution.workflow_run_id.in_(run_ids),
            )
        )
        or 0
    )
    processed = len(runs)
    qualified = _outcome_count(outcomes, "lead_qualified")
    accepted = _outcome_count(outcomes, "quote_accepted")
    won = _outcome_count(outcomes, "order_won")
    revenue = sum(
        (row.value_numeric or Decimal("0"))
        for row in outcomes
        if row.outcome_type in {"influenced_revenue", "order_won"}
        and row.status in {"observed", "confirmed", "completed"}
    )
    response_minutes = [
        Decimal(row.value_numeric)
        for row in outcomes
        if row.outcome_type == "response_time_minutes" and row.value_numeric is not None
    ]
    qualification_minutes = [
        Decimal(row.value_numeric)
        for row in outcomes
        if row.outcome_type == "time_to_qualification_minutes" and row.value_numeric is not None
    ]
    review_minutes = [
        Decimal(str((row.decided_at - row.created_at).total_seconds() / 60))
        for row in approvals
        if row.decided_at is not None
    ]
    rejected = sum(row.status == "rejected" for row in approvals)
    approved = sum(row.status == "approved" for row in approvals)
    prevented = sum(
        row.status in {"rejected", "escalated"} and row.risk_level in {"high", "critical"}
        for row in approvals
    )
    baseline_response = baseline.prior_response_time_minutes if baseline else None
    baseline_handling = baseline.manual_handling_time_minutes if baseline else None
    categories = {
        "revenue": [
            metric("qualified_leads", qualified, unit="count"),
            metric("quotes_accepted", accepted, unit="count"),
            metric("order_conversion", ratio(won, processed), unit="ratio"),
            metric("influenced_revenue", revenue, unit=baseline.currency if baseline else "NGN"),
        ],
        "cost": [
            metric("estimated_ai_cost", ai_cost, unit="currency"),
            metric("cost_per_enquiry", ratio(ai_cost, processed), unit="currency"),
            metric("cost_per_qualified_lead", ratio(ai_cost, qualified), unit="currency"),
        ],
        "speed": [
            metric(
                "median_first_response_time",
                median_minutes(response_minutes),
                unit="minutes",
                baseline=baseline_response,
            ),
            metric(
                "median_human_review_time",
                median_minutes(review_minutes),
                unit="minutes",
                baseline=baseline_handling,
            ),
            metric(
                "median_time_to_qualification",
                median_minutes(qualification_minutes),
                unit="minutes",
            ),
        ],
        "quality": [
            metric("ai_correction_rate", ratio(corrections, processed), unit="ratio"),
            metric("approval_rate", ratio(approved, len(approvals)), unit="ratio"),
            metric("rejection_rate", ratio(rejected, len(approvals)), unit="ratio"),
        ],
        "risk": [metric("unsafe_actions_prevented", prevented, unit="count")],
        "adoption": [
            metric("enquiries_processed", processed, unit="count"),
            metric("reviewed_actions", len(approvals), unit="count"),
        ],
    }
    return {
        "business_id": str(business_id),
        "workflow_key": workflow_key,
        "baseline": _baseline_view(baseline) if baseline else None,
        "categories": categories,
        "evidence": {
            "workflow_runs": processed,
            "outcomes": len(outcomes),
            "approval_records": len(approvals),
            "corrections": corrections,
        },
    }


def _outcome_count(rows: Sequence[Outcome], outcome_type: str) -> int:
    return sum(
        row.outcome_type == outcome_type and row.status in {"observed", "confirmed", "completed"}
        for row in rows
    )


def _baseline_view(row: WorkflowValueBaseline) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "workflow_key": row.workflow_key,
        "prior_response_time_minutes": _decimal(row.prior_response_time_minutes),
        "manual_handling_time_minutes": _decimal(row.manual_handling_time_minutes),
        "prior_conversion_rate": _decimal(row.prior_conversion_rate),
        "missed_lead_frequency_monthly": _decimal(row.missed_lead_frequency_monthly),
        "common_mistake_cost": _decimal(row.common_mistake_cost),
        "currency": row.currency,
        "source": row.source,
        "recorded_by": row.recorded_by,
    }


def _empty_dashboard(
    business_id: UUID,
    workflow_key: str,
    baseline: WorkflowValueBaseline | None,
) -> dict[str, Any]:
    return {
        "business_id": str(business_id),
        "workflow_key": workflow_key,
        "baseline": _baseline_view(baseline) if baseline else None,
        "categories": {
            category: [] for category in ("revenue", "cost", "speed", "quality", "risk", "adoption")
        },
        "evidence": {
            "workflow_runs": 0,
            "outcomes": 0,
            "approval_records": 0,
            "corrections": 0,
        },
    }


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
