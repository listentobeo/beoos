from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.onboarding import (
    ConfirmInferredResponse,
    OnboardingAnswer,
    OnboardingStart,
    OnboardingState,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    OnboardingResponse,
    OnboardingSession,
)
from app.services.onboarding import (
    QUESTION_BY_KEY,
    applicable_questions,
    build_draft_specification,
    completion,
    connector_disclosures,
    next_question,
)

router = APIRouter(prefix="/businesses/{business_id}/onboarding", tags=["onboarding"])


@router.post("/sessions", response_model=OnboardingState, status_code=201)
async def start_or_resume(
    business_id: UUID,
    payload: OnboardingStart,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OnboardingState:
    existing = await session.scalar(
        select(OnboardingSession)
        .where(
            OnboardingSession.business_id == business_id,
            OnboardingSession.status.in_(
                ["in_progress", "ready_for_preview", "awaiting_activation"]
            ),
        )
        .order_by(OnboardingSession.last_activity_at.desc())
    )
    if existing is not None:
        return await _state(session, existing)
    now = datetime.now(UTC)
    first = next_question(set(), payload.selected_first_problem)
    onboarding = OnboardingSession(
        business_id=business_id,
        onboarding_stage=first.stage if first else 1,
        status="in_progress",
        completion_percentage=0,
        selected_first_problem=payload.selected_first_problem,
        current_question_key=first.key if first else None,
        started_at=now,
        last_activity_at=now,
        draft_specification={},
        deployment_mode="experimental",
    )
    session.add(onboarding)
    await session.commit()
    return await _state(session, onboarding)


@router.get("/sessions/{session_id}", response_model=OnboardingState)
async def get_session_state(
    business_id: UUID,
    session_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> OnboardingState:
    onboarding = await _get_session(session, business_id, session_id)
    return await _state(session, onboarding)


@router.get("/sessions/{session_id}/connectors")
async def get_relevant_connector_disclosures(
    business_id: UUID,
    session_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> dict[str, dict[str, Any]]:
    onboarding = await _get_session(session, business_id, session_id)
    return connector_disclosures(onboarding.selected_first_problem)


@router.post("/sessions/{session_id}/responses", response_model=OnboardingState)
async def answer_question(
    business_id: UUID,
    session_id: UUID,
    payload: OnboardingAnswer,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OnboardingState:
    onboarding = await _get_session(session, business_id, session_id)
    if onboarding.status not in {"in_progress", "ready_for_preview"}:
        raise HTTPException(status_code=409, detail="Onboarding session is not accepting answers")
    question = QUESTION_BY_KEY.get(payload.question_key)
    if question is None or question not in applicable_questions(onboarding.selected_first_problem):
        raise HTTPException(status_code=400, detail="Question is not applicable")
    if payload.response_type == "skipped" and not payload.skip_explanation:
        raise HTTPException(status_code=400, detail="Skipping requires an explanation")
    response = await session.scalar(
        select(OnboardingResponse).where(
            OnboardingResponse.onboarding_session_id == onboarding.id,
            OnboardingResponse.question_key == payload.question_key,
        )
    )
    inferred = payload.source in {"website_inferred", "connector_inferred"}
    if response is None:
        response = OnboardingResponse(
            business_id=business_id,
            onboarding_session_id=onboarding.id,
            question_key=payload.question_key,
        )
        session.add(response)
    response.workflow_key = payload.workflow_key
    response.response_type = payload.response_type
    response.response_value = payload.response_value
    response.source = payload.source
    response.confidence = payload.confidence
    response.requires_confirmation = inferred
    response.confirmed_by = None if inferred else access.user_id
    response.confirmed_at = None if inferred else datetime.now(UTC)
    response.skip_explanation = payload.skip_explanation
    if payload.question_key == "problem.first":
        selected = payload.response_value.get("value")
        if isinstance(selected, str):
            onboarding.selected_first_problem = selected
    await session.flush()
    await _advance(session, onboarding)
    await session.commit()
    return await _state(session, onboarding)


@router.post("/sessions/{session_id}/confirm", response_model=OnboardingState)
async def confirm_inferred_response(
    business_id: UUID,
    session_id: UUID,
    payload: ConfirmInferredResponse,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OnboardingState:
    onboarding = await _get_session(session, business_id, session_id)
    response = await session.scalar(
        select(OnboardingResponse).where(
            OnboardingResponse.id == payload.response_id,
            OnboardingResponse.onboarding_session_id == onboarding.id,
            OnboardingResponse.business_id == business_id,
        )
    )
    if response is None or not response.requires_confirmation:
        raise HTTPException(status_code=404, detail="Pending inferred response not found")
    if payload.accepted:
        response.confirmed_by = access.user_id
        response.confirmed_at = datetime.now(UTC)
        response.requires_confirmation = False
    else:
        if payload.replacement_value is None:
            raise HTTPException(status_code=400, detail="Rejected inference needs a replacement")
        response.response_value = payload.replacement_value
        response.source = "user"
        response.confidence = Decimal("1")
        response.requires_confirmation = False
        response.confirmed_by = access.user_id
        response.confirmed_at = datetime.now(UTC)
    await _advance(session, onboarding)
    await session.commit()
    return await _state(session, onboarding)


@router.post("/sessions/{session_id}/activate", response_model=OnboardingState)
async def confirm_draft_specification(
    business_id: UUID,
    session_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> OnboardingState:
    onboarding = await _get_session(session, business_id, session_id)
    pending = await _pending_confirmations(session, onboarding.id)
    if pending:
        raise HTTPException(status_code=409, detail="Inferred answers still require confirmation")
    responses = await _response_map(session, onboarding.id)
    if responses.get("preview.confirm", {}).get("value") != "confirmed":
        raise HTTPException(status_code=409, detail="Preview must be explicitly confirmed")
    onboarding.status = "completed"
    onboarding.completed_at = datetime.now(UTC)
    onboarding.last_activity_at = onboarding.completed_at
    onboarding.activation_confirmed_by = access.user_id
    onboarding.activation_confirmed_at = onboarding.completed_at
    onboarding.deployment_mode = "experimental"
    onboarding.onboarding_stage = 8
    onboarding.completion_percentage = 100
    onboarding.current_question_key = None
    onboarding.draft_specification = {
        **build_draft_specification(responses),
        "status": "owner_approved_for_evaluation",
        "approved_by": access.user_id,
        "approved_at": onboarding.completed_at.isoformat(),
    }
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="onboarding.specification_approved",
            resource_type="onboarding_session",
            resource_id=str(onboarding.id),
            details={
                "deployment_mode": "experimental",
                "external_actions_enabled": False,
            },
        )
    )
    await session.commit()
    return await _state(session, onboarding)


async def _get_session(
    session: AsyncSession, business_id: UUID, session_id: UUID
) -> OnboardingSession:
    onboarding = await session.scalar(
        select(OnboardingSession).where(
            OnboardingSession.id == session_id,
            OnboardingSession.business_id == business_id,
        )
    )
    if onboarding is None:
        raise HTTPException(status_code=404, detail="Onboarding session not found")
    return onboarding


async def _advance(session: AsyncSession, onboarding: OnboardingSession) -> None:
    responses = await _response_map(session, onboarding.id)
    answered = set(responses)
    question = next_question(answered, onboarding.selected_first_problem)
    onboarding.completion_percentage = completion(answered, onboarding.selected_first_problem)
    onboarding.current_question_key = question.key if question else None
    onboarding.onboarding_stage = question.stage if question else 8
    onboarding.last_activity_at = datetime.now(UTC)
    onboarding.draft_specification = build_draft_specification(responses)
    onboarding.status = "ready_for_preview" if question is None else "in_progress"


async def _state(session: AsyncSession, onboarding: OnboardingSession) -> OnboardingState:
    question = (
        QUESTION_BY_KEY[onboarding.current_question_key].view()
        if onboarding.current_question_key in QUESTION_BY_KEY
        else None
    )
    return OnboardingState(
        id=onboarding.id,
        business_id=onboarding.business_id,
        stage=onboarding.onboarding_stage,
        status=onboarding.status,
        completion_percentage=onboarding.completion_percentage,
        selected_first_problem=onboarding.selected_first_problem,
        current_question=question,
        pending_confirmations=await _pending_confirmations(session, onboarding.id),
        draft_specification=onboarding.draft_specification,
        deployment_mode=onboarding.deployment_mode,
    )


async def _response_map(
    session: AsyncSession, onboarding_session_id: UUID
) -> dict[str, dict[str, Any]]:
    rows = (
        await session.scalars(
            select(OnboardingResponse).where(
                OnboardingResponse.onboarding_session_id == onboarding_session_id
            )
        )
    ).all()
    return {row.question_key: row.response_value for row in rows}


async def _pending_confirmations(session: AsyncSession, onboarding_session_id: UUID) -> int:
    value = await session.scalar(
        select(func.count(OnboardingResponse.id)).where(
            OnboardingResponse.onboarding_session_id == onboarding_session_id,
            OnboardingResponse.requires_confirmation.is_(True),
            OnboardingResponse.confirmed_at.is_(None),
        )
    )
    return int(value or 0)
