from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.learning import (
    CandidateApproval,
    DatasetCandidateCreate,
    PrivacyReview,
    SuggestionDecision,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Dataset,
    DatasetCandidate,
    DatasetExample,
    HumanCorrection,
    ImprovementSuggestion,
    WorkflowDefinition,
    WorkflowRun,
)

router = APIRouter(prefix="/businesses/{business_id}/learning", tags=["learning"])


@router.get("/candidates")
async def list_candidates(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(DatasetCandidate)
            .where(DatasetCandidate.business_id == business_id)
            .order_by(DatasetCandidate.created_at.desc())
        )
    ).all()
    return [_candidate_view(row) for row in rows]


@router.post("/candidates", status_code=201)
async def create_candidate(
    business_id: UUID,
    payload: DatasetCandidateCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    correction = await session.scalar(
        select(HumanCorrection).where(
            HumanCorrection.id == payload.human_correction_id,
            HumanCorrection.business_id == business_id,
        )
    )
    if correction is None:
        raise HTTPException(status_code=404, detail="Tenant correction not found")
    if not correction.changed_fields or correction.final_action != "edit_and_approve":
        raise HTTPException(
            status_code=409, detail="Only clear approved edits can become candidates"
        )
    run = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == correction.workflow_run_id,
            WorkflowRun.business_id == business_id,
        )
    )
    workflow = (
        await session.scalar(
            select(WorkflowDefinition).where(WorkflowDefinition.id == run.workflow_definition_id)
        )
        if run
        else None
    )
    if run is None or workflow is None or workflow.key != payload.workflow_key:
        raise HTTPException(status_code=409, detail="Correction workflow provenance is invalid")
    status = (
        "ready_for_approval"
        if payload.redaction_status == "not_required"
        and not payload.contains_personal_data
        and not payload.contains_sensitive_data
        else "pending_privacy"
    )
    candidate = DatasetCandidate(
        business_id=business_id,
        workflow_key=payload.workflow_key,
        human_correction_id=correction.id,
        workflow_run_id=run.id,
        input_payload=payload.input_payload,
        expected_output=payload.expected_output,
        correction_reason=correction.reason,
        contains_personal_data=payload.contains_personal_data,
        contains_sensitive_data=payload.contains_sensitive_data,
        redaction_status=payload.redaction_status,
        status=status,
    )
    session.add(candidate)
    await session.flush()
    await _audit(
        session,
        business_id,
        access.user_id,
        "dataset_candidate.created",
        candidate.id,
        {"correction_id": str(correction.id), "status": status},
    )
    await session.commit()
    return _candidate_view(candidate)


@router.post("/candidates/{candidate_id}/privacy-review")
async def review_candidate_privacy(
    business_id: UUID,
    candidate_id: UUID,
    payload: PrivacyReview,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    candidate = await _candidate(session, business_id, candidate_id)
    if candidate.status != "pending_privacy":
        raise HTTPException(status_code=409, detail="Candidate is not pending privacy review")
    now = datetime.now(UTC)
    candidate.privacy_reviewed_by = access.user_id
    candidate.privacy_reviewed_at = now
    if not payload.approve:
        candidate.status = "rejected"
        candidate.redaction_status = "rejected"
    else:
        if candidate.contains_personal_data or candidate.contains_sensitive_data:
            if payload.redacted_input is None or payload.redacted_output is None:
                raise HTTPException(status_code=422, detail="Redacted payloads are required")
            candidate.input_payload = payload.redacted_input
            candidate.expected_output = payload.redacted_output
            candidate.redaction_status = "redacted"
        else:
            candidate.redaction_status = "not_required"
        candidate.status = "ready_for_approval"
    await _audit(
        session,
        business_id,
        access.user_id,
        "dataset_candidate.privacy_reviewed",
        candidate.id,
        {"approved": payload.approve, "reason": payload.reason},
    )
    await session.commit()
    return _candidate_view(candidate)


@router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(
    business_id: UUID,
    candidate_id: UUID,
    payload: CandidateApproval,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    candidate = await _candidate(session, business_id, candidate_id)
    if candidate.status != "ready_for_approval":
        raise HTTPException(status_code=409, detail="Candidate has not passed privacy review")
    dataset = await session.scalar(
        select(Dataset).where(
            Dataset.id == payload.dataset_id,
            Dataset.business_id == business_id,
            Dataset.workflow_key == candidate.workflow_key,
        )
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Compatible tenant dataset not found")
    example = DatasetExample(
        dataset_id=dataset.id,
        business_id=business_id,
        source_type="human_correction",
        source_reference=str(candidate.human_correction_id),
        input_payload=candidate.input_payload,
        expected_output=candidate.expected_output,
        expected_policy_result={},
        expected_approval_requirement=False,
        labels=payload.labels,
        difficulty=payload.difficulty,
        contains_personal_data=candidate.contains_personal_data,
        redaction_status=candidate.redaction_status,
        approved_by=access.user_id,
    )
    session.add(example)
    await session.flush()
    candidate.target_dataset_id = dataset.id
    candidate.dataset_example_id = example.id
    candidate.approved_by = access.user_id
    candidate.approved_at = datetime.now(UTC)
    candidate.status = "approved"
    correction = await session.get(HumanCorrection, candidate.human_correction_id)
    if correction:
        correction.approved_for_dataset = True
    await _audit(
        session,
        business_id,
        access.user_id,
        "dataset_candidate.approved",
        candidate.id,
        {"dataset_id": str(dataset.id), "dataset_example_id": str(example.id)},
    )
    await session.commit()
    return _candidate_view(candidate)


@router.get("/suggestions")
async def list_improvement_suggestions(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(ImprovementSuggestion)
            .where(ImprovementSuggestion.business_id == business_id)
            .order_by(ImprovementSuggestion.created_at.desc())
        )
    ).all()
    return [_suggestion_view(row) for row in rows]


@router.post("/suggestions/generate")
async def generate_improvement_suggestions(
    business_id: UUID,
    workflow_key: str,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(HumanCorrection.correction_type, func.count(HumanCorrection.id))
            .join(WorkflowRun, WorkflowRun.id == HumanCorrection.workflow_run_id)
            .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowRun.workflow_definition_id)
            .where(
                HumanCorrection.business_id == business_id,
                WorkflowDefinition.key == workflow_key,
            )
            .group_by(HumanCorrection.correction_type)
            .having(func.count(HumanCorrection.id) >= 2)
        )
    ).all()
    suggestions: list[ImprovementSuggestion] = []
    for correction_type, count in rows:
        existing = await session.scalar(
            select(ImprovementSuggestion.id).where(
                ImprovementSuggestion.business_id == business_id,
                ImprovementSuggestion.workflow_key == workflow_key,
                ImprovementSuggestion.suggestion_type == correction_type,
                ImprovementSuggestion.status == "proposed",
            )
        )
        if existing:
            continue
        suggestion = ImprovementSuggestion(
            business_id=business_id,
            workflow_key=workflow_key,
            suggestion_type=correction_type,
            title=f"Review recurring {correction_type.replace('_', ' ')} corrections",
            description=(
                "Consider a policy, onboarding, extraction, permission, "
                "or prompt version proposal. No change has been applied."
            ),
            evidence=[{"source": "human_corrections", "count": int(count)}],
            occurrence_count=int(count),
            status="proposed",
        )
        session.add(suggestion)
        suggestions.append(suggestion)
    await _audit(
        session,
        business_id,
        access.user_id,
        "improvement_suggestions.generated",
        None,
        {"workflow_key": workflow_key, "count": len(suggestions)},
    )
    await session.commit()
    return [_suggestion_view(row) for row in suggestions]


@router.post("/suggestions/{suggestion_id}/decision")
async def decide_improvement_suggestion(
    business_id: UUID,
    suggestion_id: UUID,
    payload: SuggestionDecision,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    suggestion = await session.scalar(
        select(ImprovementSuggestion).where(
            ImprovementSuggestion.id == suggestion_id,
            ImprovementSuggestion.business_id == business_id,
        )
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Improvement suggestion not found")
    suggestion.status = payload.status
    suggestion.reviewed_by = access.user_id
    suggestion.reviewed_at = datetime.now(UTC)
    await _audit(
        session,
        business_id,
        access.user_id,
        "improvement_suggestion.reviewed",
        suggestion.id,
        {"status": payload.status, "reason": payload.reason, "automatic_change": False},
    )
    await session.commit()
    return _suggestion_view(suggestion)


async def _candidate(
    session: AsyncSession, business_id: UUID, candidate_id: UUID
) -> DatasetCandidate:
    row = await session.scalar(
        select(DatasetCandidate).where(
            DatasetCandidate.id == candidate_id,
            DatasetCandidate.business_id == business_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Dataset candidate not found")
    return row


async def _audit(
    session: AsyncSession,
    business_id: UUID,
    actor_id: str,
    action: str,
    resource_id: UUID | None,
    details: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=actor_id,
            action=action,
            resource_type="controlled_learning",
            resource_id=str(resource_id) if resource_id else "batch",
            details=details,
        )
    )


def _candidate_view(row: DatasetCandidate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "workflow_key": row.workflow_key,
        "human_correction_id": str(row.human_correction_id),
        "workflow_run_id": str(row.workflow_run_id),
        "target_dataset_id": str(row.target_dataset_id) if row.target_dataset_id else None,
        "contains_personal_data": row.contains_personal_data,
        "contains_sensitive_data": row.contains_sensitive_data,
        "redaction_status": row.redaction_status,
        "status": row.status,
        "privacy_reviewed_by": row.privacy_reviewed_by,
        "approved_by": row.approved_by,
        "dataset_example_id": str(row.dataset_example_id) if row.dataset_example_id else None,
    }


def _suggestion_view(row: ImprovementSuggestion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "workflow_key": row.workflow_key,
        "suggestion_type": row.suggestion_type,
        "title": row.title,
        "description": row.description,
        "evidence": row.evidence,
        "occurrence_count": row.occurrence_count,
        "status": row.status,
        "reviewed_by": row.reviewed_by,
    }
