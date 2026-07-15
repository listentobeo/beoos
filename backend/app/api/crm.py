from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.crm import (
    CRMLeadCreate,
    CRMLeadFromThread,
    CRMLeadUpdate,
    CRMLeadView,
    CRMPipelineStats,
)
from app.domain.followups import (
    FollowUpScheduleRequest,
    FollowUpScheduleResponse,
    FollowUpTaskView,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Contact,
    CRMLead,
    EmailAnalysis,
    EmailMessage,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadSource,
    LeadStage,
    MailboxConnection,
)
from app.services.follow_up_scheduler import standard_follow_up_offsets
from app.services.lead_qualification import qualify_lead

router = APIRouter(prefix="/businesses/{business_id}/crm", tags=["crm"])

OPEN_STAGES = {
    LeadStage.new,
    LeadStage.contacted,
    LeadStage.qualified,
    LeadStage.quote_needed,
    LeadStage.quoted,
    LeadStage.deposit_pending,
}


@router.get("/leads", response_model=list[CRMLeadView])
async def list_leads(
    business_id: UUID,
    stage: LeadStage | None = Query(default=None),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[CRMLeadView]:
    query = (
        select(CRMLead, Contact, EmailThread)
        .outerjoin(Contact, Contact.id == CRMLead.contact_id)
        .outerjoin(EmailThread, EmailThread.id == CRMLead.thread_id)
        .where(CRMLead.business_id == business_id)
        .order_by(CRMLead.updated_at.desc())
    )
    if stage:
        query = query.where(CRMLead.stage == stage)
    rows = (await session.execute(query)).all()
    return [_lead_view(lead, contact, thread) for lead, contact, thread in rows]


@router.get("/stats", response_model=CRMPipelineStats)
async def crm_stats(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> CRMPipelineStats:
    total = int(
        await session.scalar(
            select(func.count(CRMLead.id)).where(CRMLead.business_id == business_id)
        )
        or 0
    )
    won = int(
        await session.scalar(
            select(func.count(CRMLead.id)).where(
                CRMLead.business_id == business_id, CRMLead.stage == LeadStage.won
            )
        )
        or 0
    )
    lost = int(
        await session.scalar(
            select(func.count(CRMLead.id)).where(
                CRMLead.business_id == business_id, CRMLead.stage == LeadStage.lost
            )
        )
        or 0
    )
    open_count = int(
        await session.scalar(
            select(func.count(CRMLead.id)).where(
                CRMLead.business_id == business_id, CRMLead.stage.in_(OPEN_STAGES)
            )
        )
        or 0
    )
    value = await session.scalar(
        select(func.coalesce(func.sum(CRMLead.estimated_value), 0)).where(
            CRMLead.business_id == business_id,
            CRMLead.stage.in_(OPEN_STAGES),
        )
    )
    needs_follow_up = int(
        await session.scalar(
            select(func.count(CRMLead.id)).where(
                CRMLead.business_id == business_id,
                CRMLead.stage.in_(OPEN_STAGES),
                CRMLead.next_follow_up_at.is_not(None),
                CRMLead.next_follow_up_at <= datetime.now(UTC),
            )
        )
        or 0
    )
    return CRMPipelineStats(
        total=total,
        open=open_count,
        won=won,
        lost=lost,
        estimated_open_value=Decimal(str(value or 0)),
        needs_follow_up=needs_follow_up,
    )


@router.post("/leads", response_model=CRMLeadView, status_code=201)
async def create_lead(
    business_id: UUID,
    payload: CRMLeadCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> CRMLeadView:
    if payload.contact_id:
        await _ensure_contact(session, business_id, payload.contact_id)
    if payload.thread_id:
        await _ensure_thread(session, business_id, payload.thread_id)
    lead = CRMLead(
        business_id=business_id,
        contact_id=payload.contact_id,
        thread_id=payload.thread_id,
        title=payload.title,
        stage=payload.stage,
        source=payload.source,
        service=payload.service,
        budget=payload.budget,
        deadline=payload.deadline,
        estimated_value=payload.estimated_value,
        currency=payload.currency.upper(),
        probability=payload.probability,
        lead_score=payload.lead_score,
        temperature=payload.temperature,
        qualification_summary=payload.qualification_summary,
        qualification_reasons=payload.qualification_reasons,
        next_follow_up_at=payload.next_follow_up_at,
        notes=payload.notes,
        owner_id=access.user_id,
        closed_at=_closed_at(payload.stage),
    )
    session.add(lead)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="crm_lead.created",
            resource_type="crm_lead",
            resource_id=str(lead.id),
            details={"source": lead.source.value, "stage": lead.stage.value},
        )
    )
    await session.commit()
    return await _get_lead_view(session, business_id, lead.id)


@router.post("/threads/{thread_id}/lead", response_model=CRMLeadView, status_code=201)
async def create_lead_from_thread(
    business_id: UUID,
    thread_id: UUID,
    payload: CRMLeadFromThread,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> CRMLeadView:
    thread = await _ensure_thread(session, business_id, thread_id)
    existing = await session.scalar(
        select(CRMLead.id).where(CRMLead.business_id == business_id, CRMLead.thread_id == thread_id)
    )
    if existing:
        return await _get_lead_view(session, business_id, existing)
    analysis = await _latest_analysis(session, thread_id)
    extracted = analysis.extracted_fields if analysis else {}
    source = await _thread_source(session, thread_id)
    qualification = qualify_lead(
        thread=thread,
        analysis=analysis,
        requested_stage=payload.stage,
    )
    lead = CRMLead(
        business_id=business_id,
        contact_id=thread.contact_id,
        thread_id=thread.id,
        title=thread.subject[:240] or "New lead",
        stage=qualification.stage,
        source=source,
        service=_field(extracted, "service"),
        budget=_field(extracted, "budget"),
        deadline=_field(extracted, "deadline"),
        estimated_value=None,
        currency="NGN",
        probability=qualification.score,
        lead_score=qualification.score,
        temperature=qualification.temperature,
        qualification_summary=qualification.summary,
        qualification_reasons=qualification.reasons,
        last_qualified_at=qualification.qualified_at,
        notes=payload.notes or qualification.summary,
        owner_id=access.user_id,
        closed_at=_closed_at(qualification.stage),
    )
    session.add(lead)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="crm_lead.created_from_thread",
            resource_type="crm_lead",
            resource_id=str(lead.id),
            details={"thread_id": str(thread.id), "source": source.value},
        )
    )
    await session.commit()
    return await _get_lead_view(session, business_id, lead.id)


@router.patch("/leads/{lead_id}", response_model=CRMLeadView)
async def update_lead(
    business_id: UUID,
    lead_id: UUID,
    payload: CRMLeadUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> CRMLeadView:
    lead = await session.scalar(
        select(CRMLead).where(CRMLead.id == lead_id, CRMLead.business_id == business_id)
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    old_stage = lead.stage
    lead.title = payload.title
    lead.stage = payload.stage
    lead.service = payload.service
    lead.budget = payload.budget
    lead.deadline = payload.deadline
    lead.estimated_value = payload.estimated_value
    lead.currency = payload.currency.upper()
    lead.probability = payload.probability
    lead.lead_score = payload.lead_score
    lead.temperature = payload.temperature
    lead.qualification_summary = payload.qualification_summary
    lead.qualification_reasons = payload.qualification_reasons
    lead.last_qualified_at = datetime.now(UTC)
    lead.next_follow_up_at = payload.next_follow_up_at
    lead.notes = payload.notes
    lead.closed_at = _closed_at(payload.stage)
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="crm_lead.updated",
            resource_type="crm_lead",
            resource_id=str(lead.id),
            details={"old_stage": old_stage.value, "new_stage": lead.stage.value},
        )
    )
    await session.commit()
    return await _get_lead_view(session, business_id, lead.id)


@router.get("/follow-ups", response_model=list[FollowUpTaskView])
async def list_follow_ups(
    business_id: UUID,
    status: FollowUpStatus | None = Query(default=None),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[FollowUpTaskView]:
    query = (
        select(FollowUpTask)
        .where(FollowUpTask.business_id == business_id)
        .order_by(FollowUpTask.scheduled_for.asc())
    )
    if status:
        query = query.where(FollowUpTask.status == status)
    tasks = (await session.scalars(query)).all()
    return [_task_view(task) for task in tasks]


@router.post(
    "/leads/{lead_id}/follow-ups",
    response_model=FollowUpScheduleResponse,
    status_code=201,
)
async def schedule_follow_ups(
    business_id: UUID,
    lead_id: UUID,
    payload: FollowUpScheduleRequest,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> FollowUpScheduleResponse:
    lead = await session.scalar(
        select(CRMLead).where(CRMLead.id == lead_id, CRMLead.business_id == business_id)
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    if lead.stage not in OPEN_STAGES:
        raise HTTPException(status_code=400, detail="Closed leads cannot be scheduled")
    if lead.thread_id is None:
        raise HTTPException(status_code=400, detail="Lead has no inbox thread to follow up")

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
        task.error = "Replaced by a new follow-up sequence"

    tasks = [
        FollowUpTask(
            business_id=business_id,
            lead_id=lead.id,
            thread_id=lead.thread_id,
            contact_id=lead.contact_id,
            sequence_name=payload.cadence,
            step_number=index,
            channel="email",
            status=FollowUpStatus.scheduled,
            scheduled_for=now + offset,
            subject="",
            body_text="",
            task_metadata={"created_by": access.user_id},
        )
        for index, offset in enumerate(standard_follow_up_offsets(payload.cadence), start=1)
    ]
    session.add_all(tasks)
    lead.next_follow_up_at = tasks[0].scheduled_for
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="follow_up.sequence_scheduled",
            resource_type="crm_lead",
            resource_id=str(lead.id),
            details={
                "cadence": payload.cadence,
                "tasks_created": len(tasks),
                "cancelled_existing": len(existing),
            },
        )
    )
    await session.commit()
    for task in tasks:
        await session.refresh(task)
    return FollowUpScheduleResponse(
        success=True,
        cancelled_existing=len(existing),
        tasks_created=len(tasks),
        tasks=[_task_view(task) for task in tasks],
    )


@router.post("/follow-ups/{task_id}/cancel", response_model=FollowUpTaskView)
async def cancel_follow_up(
    business_id: UUID,
    task_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> FollowUpTaskView:
    task = await session.scalar(
        select(FollowUpTask).where(
            FollowUpTask.id == task_id,
            FollowUpTask.business_id == business_id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Follow-up task not found")
    if task.status != FollowUpStatus.scheduled:
        raise HTTPException(status_code=400, detail="Only scheduled follow-ups can be cancelled")
    task.status = FollowUpStatus.cancelled
    task.completed_at = datetime.now(UTC)
    task.error = "Cancelled manually"
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="follow_up.cancelled",
            resource_type="follow_up_task",
            resource_id=str(task.id),
            details={"lead_id": str(task.lead_id)},
        )
    )
    await session.commit()
    await session.refresh(task)
    return _task_view(task)


async def _ensure_contact(session: AsyncSession, business_id: UUID, contact_id: UUID) -> Contact:
    contact = await session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.business_id == business_id)
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


async def _ensure_thread(session: AsyncSession, business_id: UUID, thread_id: UUID) -> EmailThread:
    thread = await session.scalar(
        select(EmailThread).where(
            EmailThread.id == thread_id,
            EmailThread.business_id == business_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


async def _latest_analysis(session: AsyncSession, thread_id: UUID) -> EmailAnalysis | None:
    return await session.scalar(
        select(EmailAnalysis)
        .join(EmailMessage, EmailMessage.id == EmailAnalysis.message_id)
        .where(EmailMessage.thread_id == thread_id)
        .order_by(EmailAnalysis.created_at.desc())
        .limit(1)
    )


async def _thread_source(session: AsyncSession, thread_id: UUID) -> LeadSource:
    provider = await session.scalar(
        select(MailboxConnection.provider)
        .join(EmailMessage, EmailMessage.mailbox_id == MailboxConnection.id)
        .where(EmailMessage.thread_id == thread_id)
        .order_by(EmailMessage.sent_at.desc())
        .limit(1)
    )
    if provider == "whatsapp":
        return LeadSource.whatsapp
    if provider == "gmail":
        return LeadSource.gmail
    if provider == "form":
        return LeadSource.website_form
    if provider == "zoho":
        return LeadSource.zoho
    return LeadSource.email


async def _get_lead_view(session: AsyncSession, business_id: UUID, lead_id: UUID) -> CRMLeadView:
    row = (
        await session.execute(
            select(CRMLead, Contact, EmailThread)
            .outerjoin(Contact, Contact.id == CRMLead.contact_id)
            .outerjoin(EmailThread, EmailThread.id == CRMLead.thread_id)
            .where(CRMLead.id == lead_id, CRMLead.business_id == business_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead, contact, thread = row
    return _lead_view(lead, contact, thread)


def _lead_view(
    lead: CRMLead,
    contact: Contact | None,
    thread: EmailThread | None,
) -> CRMLeadView:
    return CRMLeadView(
        id=lead.id,
        business_id=lead.business_id,
        contact_id=lead.contact_id,
        thread_id=lead.thread_id,
        title=lead.title,
        stage=lead.stage,
        source=lead.source,
        service=lead.service,
        budget=lead.budget,
        deadline=lead.deadline,
        estimated_value=lead.estimated_value,
        currency=lead.currency,
        probability=lead.probability,
        lead_score=lead.lead_score,
        temperature=lead.temperature,
        qualification_summary=lead.qualification_summary,
        qualification_reasons=lead.qualification_reasons,
        last_qualified_at=lead.last_qualified_at,
        next_follow_up_at=lead.next_follow_up_at,
        notes=lead.notes,
        owner_id=lead.owner_id,
        closed_at=lead.closed_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        contact_name=contact.name if contact else None,
        contact_email=contact.email if contact else None,
        contact_phone=contact.phone if contact else None,
        thread_subject=thread.subject if thread else None,
    )


def _task_view(task: FollowUpTask) -> FollowUpTaskView:
    return FollowUpTaskView(
        id=task.id,
        business_id=task.business_id,
        lead_id=task.lead_id,
        thread_id=task.thread_id,
        contact_id=task.contact_id,
        sequence_name=task.sequence_name,
        step_number=task.step_number,
        channel=task.channel,
        status=task.status,
        scheduled_for=task.scheduled_for,
        completed_at=task.completed_at,
        subject=task.subject,
        body_text=task.body_text,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _field(values: dict[str, object], key: str) -> str | None:
    value = values.get(key)
    return str(value).strip() if value else None


def _closed_at(stage: LeadStage) -> datetime | None:
    return datetime.now(UTC) if stage in {LeadStage.won, LeadStage.lost} else None
