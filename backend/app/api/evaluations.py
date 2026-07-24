from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.evaluations import (
    ENQUIRY_EVALUATION_DIMENSIONS,
    DatasetCreate,
    DatasetExampleCreate,
    EvaluationResultCreate,
    EvaluationRunCreate,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Dataset,
    DatasetExample,
    EvaluationResult,
    EvaluationRun,
    HumanCorrection,
    WorkflowDefinition,
    WorkflowRun,
)

router = APIRouter(prefix="/businesses/{business_id}/evaluation", tags=["evaluation"])


@router.get("/dimensions")
async def evaluation_dimensions(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
) -> dict[str, Any]:
    return {
        "business_id": str(business_id),
        "workflow_key": "beo_art_commission_enquiry_v1",
        "dimensions": list(ENQUIRY_EVALUATION_DIMENSIONS),
        "evaluators": ["exact", "rule", "schema", "human", "model_assisted"],
        "model_assisted_policy": "Use only where deterministic grading is insufficient.",
    }


@router.get("/datasets")
async def list_datasets(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(Dataset)
            .where(or_(Dataset.business_id == business_id, Dataset.business_id.is_(None)))
            .order_by(Dataset.workflow_key, Dataset.name, Dataset.version.desc())
        )
    ).all()
    return [_dataset_view(item) for item in rows]


@router.post("/datasets", status_code=201)
async def create_dataset(
    business_id: UUID,
    payload: DatasetCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    version = int(
        await session.scalar(
            select(func.coalesce(func.max(Dataset.version), 0)).where(
                Dataset.business_id == business_id,
                Dataset.name == payload.name,
            )
        )
        or 0
    ) + 1
    dataset = Dataset(
        business_id=business_id,
        name=payload.name,
        description=payload.description,
        workflow_key=payload.workflow_key,
        scope=payload.scope,
        version=version,
        status=payload.status,
        created_by=access.user_id,
    )
    session.add(dataset)
    await session.flush()
    await _audit(
        session,
        business_id,
        access.user_id,
        "dataset.created",
        "dataset",
        dataset.id,
        {"version": version, "scope": dataset.scope},
    )
    await session.commit()
    return _dataset_view(dataset)


@router.get("/datasets/{dataset_id}/examples")
async def list_dataset_examples(
    business_id: UUID,
    dataset_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    dataset = await _dataset(session, business_id, dataset_id)
    rows = (
        await session.scalars(
            select(DatasetExample)
            .where(DatasetExample.dataset_id == dataset.id)
            .order_by(DatasetExample.created_at)
        )
    ).all()
    return [_example_view(item) for item in rows]


@router.post("/datasets/{dataset_id}/examples", status_code=201)
async def create_dataset_example(
    business_id: UUID,
    dataset_id: UUID,
    payload: DatasetExampleCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    dataset = await _dataset(session, business_id, dataset_id)
    if dataset.business_id is None:
        raise HTTPException(status_code=403, detail="Global datasets are platform-managed")
    await _validate_source_reference(session, business_id, payload)
    approved = payload.redaction_status in {"not_required", "redacted"}
    example = DatasetExample(
        dataset_id=dataset.id,
        business_id=business_id,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        input_payload=payload.input_payload,
        expected_output=payload.expected_output,
        expected_policy_result=payload.expected_policy_result,
        expected_approval_requirement=payload.expected_approval_requirement,
        labels=payload.labels,
        difficulty=payload.difficulty,
        contains_personal_data=payload.contains_personal_data,
        redaction_status=payload.redaction_status,
        approved_by=access.user_id if approved else None,
    )
    session.add(example)
    await session.flush()
    await _audit(
        session,
        business_id,
        access.user_id,
        "dataset_example.created",
        "dataset_example",
        example.id,
        {
            "dataset_id": str(dataset.id),
            "redaction_status": example.redaction_status,
            "contains_personal_data": example.contains_personal_data,
        },
    )
    await session.commit()
    return _example_view(example)


@router.post("/runs", status_code=201)
async def create_evaluation_run(
    business_id: UUID,
    payload: EvaluationRunCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    dataset = await _dataset(session, business_id, payload.dataset_id)
    if dataset.status != "active":
        raise HTTPException(status_code=409, detail="Evaluation dataset is not active")
    pending_private = await session.scalar(
        select(func.count(DatasetExample.id)).where(
            DatasetExample.dataset_id == dataset.id,
            or_(
                DatasetExample.redaction_status.in_(["pending", "rejected"]),
                (
                    DatasetExample.contains_personal_data.is_(True)
                    & (DatasetExample.redaction_status != "redacted")
                ),
            ),
        )
    )
    if int(pending_private or 0):
        raise HTTPException(status_code=409, detail="Dataset has unapproved privacy review")
    workflow = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.id == payload.workflow_definition_id,
            or_(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.business_id.is_(None),
            ),
            WorkflowDefinition.key == dataset.workflow_key,
        )
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="Compatible workflow definition not found")
    total = int(
        await session.scalar(
            select(func.count(DatasetExample.id)).where(
                DatasetExample.dataset_id == dataset.id,
                DatasetExample.approved_by.is_not(None),
            )
        )
        or 0
    )
    run = EvaluationRun(
        business_id=business_id,
        workflow_definition_id=workflow.id,
        workflow_version=workflow.version,
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        model=payload.model,
        prompt_version=payload.prompt_version,
        policy_version=payload.policy_version,
        status="queued",
        total_examples=total,
        passed=0,
        failed=0,
        estimated_cost=Decimal("0"),
        average_latency=0,
        summary={
            "dimensions": list(ENQUIRY_EVALUATION_DIMENSIONS),
            "grading_policy": "deterministic_first",
        },
    )
    session.add(run)
    await session.flush()
    await _audit(
        session,
        business_id,
        access.user_id,
        "evaluation_run.created",
        "evaluation_run",
        run.id,
        {"dataset_id": str(dataset.id), "workflow_definition_id": str(workflow.id)},
    )
    await session.commit()
    return _run_view(run)


@router.get("/runs")
async def list_evaluation_runs(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (
        await session.scalars(
            select(EvaluationRun)
            .where(EvaluationRun.business_id == business_id)
            .order_by(EvaluationRun.created_at.desc())
        )
    ).all()
    return [_run_view(item) for item in rows]


@router.post("/runs/{run_id}/results", status_code=201)
async def record_evaluation_result(
    business_id: UUID,
    run_id: UUID,
    payload: EvaluationResultCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    run = await session.scalar(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id, EvaluationRun.business_id == business_id
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    example = await session.scalar(
        select(DatasetExample).where(
            DatasetExample.id == payload.dataset_example_id,
            DatasetExample.dataset_id == run.dataset_id,
        )
    )
    if example is None:
        raise HTTPException(status_code=404, detail="Dataset example not found")
    if example.approved_by is None:
        raise HTTPException(status_code=409, detail="Dataset example is not approved")
    existing = await session.scalar(
        select(EvaluationResult).where(
            EvaluationResult.evaluation_run_id == run.id,
            EvaluationResult.dataset_example_id == example.id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Example already has a result in this run")
    result = EvaluationResult(
        business_id=business_id,
        evaluation_run_id=run.id,
        dataset_example_id=example.id,
        actual_output=payload.actual_output,
        pass_fail=payload.pass_fail,
        scores={
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in payload.scores.items()
        },
        failure_type=payload.failure_type,
        evaluator_type=payload.evaluator_type,
        evaluator_notes=payload.evaluator_notes,
        human_reviewed=payload.human_reviewed,
    )
    session.add(result)
    run.passed += 1 if result.pass_fail else 0
    run.failed += 0 if result.pass_fail else 1
    if run.passed + run.failed >= run.total_examples:
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
    elif run.status == "queued":
        run.status = "running"
        run.started_at = datetime.now(UTC)
    await session.commit()
    return {
        "id": str(result.id),
        "pass_fail": result.pass_fail,
        "evaluator_type": result.evaluator_type,
        "human_reviewed": result.human_reviewed,
    }


async def _dataset(
    session: AsyncSession, business_id: UUID, dataset_id: UUID
) -> Dataset:
    dataset = await session.scalar(
        select(Dataset).where(
            Dataset.id == dataset_id,
            or_(Dataset.business_id == business_id, Dataset.business_id.is_(None)),
        )
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


async def _validate_source_reference(
    session: AsyncSession,
    business_id: UUID,
    payload: DatasetExampleCreate,
) -> None:
    if payload.source_type not in {"workflow_run", "human_correction"}:
        return
    try:
        source_id = UUID(payload.source_reference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Source reference must be a UUID") from exc
    if payload.source_type == "workflow_run":
        exists_for_tenant = await session.scalar(
            select(WorkflowRun.id).where(
                WorkflowRun.id == source_id, WorkflowRun.business_id == business_id
            )
        )
    else:
        exists_for_tenant = await session.scalar(
            select(HumanCorrection.id).where(
                HumanCorrection.id == source_id,
                HumanCorrection.business_id == business_id,
            )
        )
    if exists_for_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant-owned source reference not found")


async def _audit(
    session: AsyncSession,
    business_id: UUID,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: UUID,
    details: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=details,
        )
    )


def _dataset_view(dataset: Dataset) -> dict[str, Any]:
    return {
        "id": str(dataset.id),
        "business_id": str(dataset.business_id) if dataset.business_id else None,
        "name": dataset.name,
        "description": dataset.description,
        "workflow_key": dataset.workflow_key,
        "scope": dataset.scope,
        "version": dataset.version,
        "status": dataset.status,
        "created_by": dataset.created_by,
        "created_at": dataset.created_at,
    }


def _example_view(example: DatasetExample) -> dict[str, Any]:
    return {
        "id": str(example.id),
        "dataset_id": str(example.dataset_id),
        "business_id": str(example.business_id) if example.business_id else None,
        "source_type": example.source_type,
        "source_reference": example.source_reference,
        "input_payload": example.input_payload,
        "expected_output": example.expected_output,
        "expected_policy_result": example.expected_policy_result,
        "expected_approval_requirement": example.expected_approval_requirement,
        "labels": example.labels,
        "difficulty": example.difficulty,
        "contains_personal_data": example.contains_personal_data,
        "redaction_status": example.redaction_status,
        "approved_by": example.approved_by,
        "created_at": example.created_at,
    }


def _run_view(run: EvaluationRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "business_id": str(run.business_id),
        "workflow_definition_id": str(run.workflow_definition_id),
        "workflow_version": run.workflow_version,
        "dataset_id": str(run.dataset_id),
        "dataset_version": run.dataset_version,
        "model": run.model,
        "prompt_version": run.prompt_version,
        "policy_version": run.policy_version,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "total_examples": run.total_examples,
        "passed": run.passed,
        "failed": run.failed,
        "estimated_cost": str(run.estimated_cost),
        "average_latency": run.average_latency,
        "summary": run.summary,
    }
