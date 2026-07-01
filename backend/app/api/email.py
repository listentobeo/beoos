from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.email import (
    DraftQueueItem,
    DraftView,
    InboxStats,
    ThreadDetail,
    ThreadListItem,
    ThreadMessageView,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    Contact,
    DraftStatus,
    EmailDraft,
    EmailThread,
    ThreadCategory,
    ThreadStatus,
)
from app.services.email_sync import EmailSyncService

router = APIRouter(prefix="/businesses/{business_id}/email", tags=["email"])


@router.get("/threads", response_model=list[ThreadListItem])
async def list_threads(
    business_id: UUID,
    category: ThreadCategory | None = None,
    status: ThreadStatus | None = None,
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[ThreadListItem]:
    query = (
        select(EmailThread)
        .options(selectinload(EmailThread.contact))
        .where(EmailThread.business_id == business_id)
        .order_by(EmailThread.priority.desc(), EmailThread.latest_message_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if category:
        query = query.where(EmailThread.category == category)
    if status:
        query = query.where(EmailThread.status == status)
    if search:
        query = query.outerjoin(Contact).where(
            EmailThread.subject.ilike(f"%{search}%") | Contact.email.ilike(f"%{search}%")
        )
    threads = (await session.scalars(query)).all()
    return [_thread_view(thread) for thread in threads]


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    business_id: UUID,
    thread_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> ThreadDetail:
    thread = await session.scalar(
        select(EmailThread)
        .options(selectinload(EmailThread.contact), selectinload(EmailThread.messages))
        .where(EmailThread.id == thread_id, EmailThread.business_id == business_id)
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    drafts = (
        await session.scalars(
            select(EmailDraft)
            .where(EmailDraft.thread_id == thread.id)
            .order_by(EmailDraft.created_at.desc())
        )
    ).all()
    return ThreadDetail(
        thread=_thread_view(thread),
        messages=[
            ThreadMessageView(
                id=message.id,
                direction=message.direction.value,
                sender_email=message.sender_email,
                sender_name=message.sender_name,
                subject=message.subject,
                body_text=message.body_text,
                sent_at=message.sent_at,
            )
            for message in thread.messages
        ],
        drafts=[
            DraftView(
                id=draft.id,
                subject=draft.subject,
                body_text=draft.body_text,
                status=draft.status.value,
                draft_type=draft.draft_type,
                auto_send_eligible=draft.auto_send_eligible,
                policy_reasons=draft.policy_reasons,
            )
            for draft in drafts
        ],
    )


@router.get("/stats", response_model=InboxStats)
async def inbox_stats(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> InboxStats:
    async def count(*conditions: ColumnElement[bool]) -> int:
        value = await session.scalar(
            select(func.count(EmailThread.id)).where(
                EmailThread.business_id == business_id, *conditions
            )
        )
        return int(value or 0)

    unread_value = await session.scalar(
        select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
            EmailThread.business_id == business_id
        )
    )
    return InboxStats(
        unread=int(unread_value or 0),
        needs_approval=await count(EmailThread.status == ThreadStatus.needs_approval),
        urgent=await count(EmailThread.category == ThreadCategory.urgent),
        routed_whatsapp=await count(EmailThread.status == ThreadStatus.routed_whatsapp),
        existing_clients=await count(EmailThread.category == ThreadCategory.existing_client),
    )


@router.get("/drafts", response_model=list[DraftQueueItem])
async def list_pending_drafts(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[DraftQueueItem]:
    rows = (
        await session.execute(
            select(EmailDraft, EmailThread, Contact)
            .join(EmailThread, EmailThread.id == EmailDraft.thread_id)
            .outerjoin(Contact, Contact.id == EmailThread.contact_id)
            .where(
                EmailThread.business_id == business_id,
                EmailDraft.status == DraftStatus.pending,
            )
            .order_by(EmailDraft.created_at.desc())
        )
    ).all()
    return [
        DraftQueueItem(
            id=draft.id,
            thread_id=thread.id,
            thread_subject=thread.subject,
            subject=draft.subject,
            body_text=draft.body_text,
            status=draft.status.value,
            draft_type=draft.draft_type,
            auto_send_eligible=draft.auto_send_eligible,
            policy_reasons=draft.policy_reasons,
            category=thread.category,
            contact_name=contact.name if contact else None,
            contact_email=contact.email if contact else None,
            created_at=draft.created_at,
        )
        for draft, thread, contact in rows
    ]


@router.post("/threads/{thread_id}/mark-read", status_code=204)
async def mark_thread_read(
    business_id: UUID,
    thread_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> None:
    thread = await session.scalar(
        select(EmailThread).where(
            EmailThread.id == thread_id,
            EmailThread.business_id == business_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.unread_count = 0
    await session.commit()


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(
    business_id: UUID,
    draft_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    draft = await session.scalar(
        select(EmailDraft)
        .join(EmailThread, EmailThread.id == EmailDraft.thread_id)
        .where(EmailDraft.id == draft_id, EmailThread.business_id == business_id)
        .with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status.value not in {"pending", "rejected", "failed"}:
        raise HTTPException(status_code=409, detail="Draft is not awaiting approval")
    service = EmailSyncService(settings)
    try:
        await service.send_approved_draft(session, draft, actor_id=access.user_id)
    finally:
        await service.close()
    return {"status": "sent", "draft_id": str(draft.id)}


def _thread_view(thread: EmailThread) -> ThreadListItem:
    return ThreadListItem(
        id=thread.id,
        subject=thread.subject,
        contact_name=thread.contact.name if thread.contact else None,
        contact_email=thread.contact.email if thread.contact else None,
        category=thread.category,
        status=thread.status,
        priority=thread.priority,
        is_deal=thread.is_deal,
        is_professional=thread.is_professional,
        unread_count=thread.unread_count,
        latest_message_at=thread.latest_message_at,
    )
