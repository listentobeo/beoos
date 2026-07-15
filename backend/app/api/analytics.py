from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.security import BusinessAccess, require_business_access
from app.domain.analytics import (
    AnalyticsBucket,
    AnalyticsConversion,
    AnalyticsRecentActivity,
    AnalyticsSummary,
    AnalyticsTotals,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    CRMLead,
    Direction,
    DraftStatus,
    EmailDraft,
    EmailMessage,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadStage,
    MailboxConnection,
    Quote,
    QuoteStatus,
    ThreadStatus,
)

router = APIRouter(prefix="/businesses/{business_id}/analytics", tags=["analytics"])

OPEN_LEAD_STAGES = {
    LeadStage.new,
    LeadStage.contacted,
    LeadStage.qualified,
    LeadStage.quote_needed,
    LeadStage.quoted,
    LeadStage.deposit_pending,
}

OPEN_QUOTE_STATUSES = {
    QuoteStatus.draft,
    QuoteStatus.needs_approval,
    QuoteStatus.approved,
    QuoteStatus.sent,
}


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    business_id: UUID,
    window_days: int = Query(default=30, ge=1, le=365),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> AnalyticsSummary:
    now = datetime.now(UTC)
    since = now - timedelta(days=window_days)

    conversations = await _count(
        session,
        EmailThread.id,
        EmailThread.business_id == business_id,
        EmailThread.latest_message_at >= since,
    )
    inbound_messages = await _message_count(
        session,
        business_id,
        since,
        EmailMessage.direction == Direction.inbound,
    )
    outbound_messages = await _message_count(
        session,
        business_id,
        since,
        EmailMessage.direction == Direction.outbound,
    )
    unread_messages = int(
        await session.scalar(
            select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
                EmailThread.business_id == business_id
            )
        )
        or 0
    )
    needs_approval = await _count(
        session,
        EmailThread.id,
        EmailThread.business_id == business_id,
        EmailThread.status == ThreadStatus.needs_approval,
    )
    pending_drafts = await _count_joined_drafts(session, business_id)
    due_followups = await _count(
        session,
        FollowUpTask.id,
        FollowUpTask.business_id == business_id,
        FollowUpTask.status == FollowUpStatus.scheduled,
        FollowUpTask.scheduled_for <= now,
    )
    leads_created = await _count(
        session,
        CRMLead.id,
        CRMLead.business_id == business_id,
        CRMLead.created_at >= since,
    )
    quotes_created = await _count(
        session,
        Quote.id,
        Quote.business_id == business_id,
        Quote.created_at >= since,
    )
    quotes_accepted = await _count(
        session,
        Quote.id,
        Quote.business_id == business_id,
        Quote.status == QuoteStatus.accepted,
        Quote.accepted_at >= since,
    )
    open_quote_value = await _sum_decimal(
        session,
        select(func.coalesce(func.sum(Quote.total), 0)).where(
            Quote.business_id == business_id,
            Quote.status.in_(OPEN_QUOTE_STATUSES),
        ),
    )
    accepted_quote_value = await _sum_decimal(
        session,
        select(func.coalesce(func.sum(Quote.total), 0)).where(
            Quote.business_id == business_id,
            Quote.status == QuoteStatus.accepted,
        ),
    )

    return AnalyticsSummary(
        window_days=window_days,
        totals=AnalyticsTotals(
            conversations=conversations,
            inbound_messages=inbound_messages,
            outbound_messages=outbound_messages,
            unread_messages=unread_messages,
            needs_approval=needs_approval,
            leads=leads_created,
            quotes=quotes_created,
            pending_drafts=pending_drafts,
            due_followups=due_followups,
        ),
        conversion=AnalyticsConversion(
            leads_created=leads_created,
            quotes_created=quotes_created,
            quotes_accepted=quotes_accepted,
            lead_to_quote_rate=_rate(quotes_created, leads_created),
            quote_acceptance_rate=_rate(quotes_accepted, quotes_created),
            open_quote_value=open_quote_value,
            accepted_quote_value=accepted_quote_value,
        ),
        inbox_by_provider=await _provider_buckets(session, business_id, since),
        thread_statuses=await _group_buckets(
            session,
            select(EmailThread.status, func.count(EmailThread.id))
            .where(EmailThread.business_id == business_id)
            .group_by(EmailThread.status),
        ),
        lead_sources=await _group_buckets(
            session,
            select(CRMLead.source, func.count(CRMLead.id))
            .where(CRMLead.business_id == business_id, CRMLead.created_at >= since)
            .group_by(CRMLead.source),
        ),
        lead_stages=await _group_buckets(
            session,
            select(CRMLead.stage, func.count(CRMLead.id))
            .where(CRMLead.business_id == business_id)
            .group_by(CRMLead.stage),
        ),
        lead_temperatures=await _group_buckets(
            session,
            select(CRMLead.temperature, func.count(CRMLead.id))
            .where(CRMLead.business_id == business_id, CRMLead.stage.in_(OPEN_LEAD_STAGES))
            .group_by(CRMLead.temperature),
        ),
        quote_statuses=await _quote_status_buckets(session, business_id),
        follow_up_statuses=await _group_buckets(
            session,
            select(FollowUpTask.status, func.count(FollowUpTask.id))
            .where(FollowUpTask.business_id == business_id, FollowUpTask.created_at >= since)
            .group_by(FollowUpTask.status),
        ),
        recent_activity=await _recent_activity(session, business_id),
    )


async def _count(
    session: AsyncSession,
    column: Any,
    *conditions: ColumnElement[bool],
) -> int:
    value = await session.scalar(select(func.count(column)).where(*conditions))
    return int(value or 0)


async def _message_count(
    session: AsyncSession,
    business_id: UUID,
    since: datetime,
    *conditions: ColumnElement[bool],
) -> int:
    value = await session.scalar(
        select(func.count(EmailMessage.id))
        .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
        .where(
            EmailThread.business_id == business_id,
            EmailMessage.sent_at >= since,
            *conditions,
        )
    )
    return int(value or 0)


async def _count_joined_drafts(session: AsyncSession, business_id: UUID) -> int:
    value = await session.scalar(
        select(func.count(EmailDraft.id))
        .join(EmailThread, EmailThread.id == EmailDraft.thread_id)
        .where(
            EmailThread.business_id == business_id,
            EmailDraft.status == DraftStatus.pending,
        )
    )
    return int(value or 0)


async def _sum_decimal(session: AsyncSession, statement: Select[tuple[Any]]) -> Decimal:
    value = await session.scalar(statement)
    return Decimal(str(value or 0))


async def _provider_buckets(
    session: AsyncSession,
    business_id: UUID,
    since: datetime,
) -> list[AnalyticsBucket]:
    rows = (
        await session.execute(
            select(MailboxConnection.provider, func.count(EmailMessage.id))
            .join(EmailMessage, EmailMessage.mailbox_id == MailboxConnection.id)
            .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
            .where(
                MailboxConnection.business_id == business_id,
                EmailThread.business_id == business_id,
                EmailMessage.sent_at >= since,
            )
            .group_by(MailboxConnection.provider)
        )
    ).all()
    return [_bucket(key, count) for key, count in rows]


async def _quote_status_buckets(session: AsyncSession, business_id: UUID) -> list[AnalyticsBucket]:
    rows = (
        await session.execute(
            select(Quote.status, func.count(Quote.id), func.coalesce(func.sum(Quote.total), 0))
            .where(Quote.business_id == business_id)
            .group_by(Quote.status)
        )
    ).all()
    return [
        AnalyticsBucket(
            key=_key(status),
            label=_label(status),
            count=int(count or 0),
            value=Decimal(str(value or 0)),
        )
        for status, count, value in rows
    ]


async def _group_buckets(
    session: AsyncSession,
    statement: Select[tuple[Any, Any]],
) -> list[AnalyticsBucket]:
    rows = (await session.execute(statement)).all()
    return [_bucket(key, count) for key, count in rows]


async def _recent_activity(
    session: AsyncSession,
    business_id: UUID,
) -> list[AnalyticsRecentActivity]:
    thread_rows = (
        await session.execute(
            select(EmailThread.id, EmailThread.subject, EmailThread.latest_message_at)
            .where(EmailThread.business_id == business_id)
            .order_by(EmailThread.latest_message_at.desc())
            .limit(5)
        )
    ).all()
    lead_rows = (
        await session.execute(
            select(CRMLead.id, CRMLead.title, CRMLead.updated_at)
            .where(CRMLead.business_id == business_id)
            .order_by(CRMLead.updated_at.desc())
            .limit(5)
        )
    ).all()
    quote_rows = (
        await session.execute(
            select(Quote.id, Quote.title, Quote.updated_at)
            .where(Quote.business_id == business_id)
            .order_by(Quote.updated_at.desc())
            .limit(5)
        )
    ).all()

    activity = [
        AnalyticsRecentActivity(
            label="Inbox conversation",
            detail=subject,
            occurred_at=occurred_at,
            href=f"/dashboard/inbox/{thread_id}",
        )
        for thread_id, subject, occurred_at in thread_rows
    ]
    activity.extend(
        AnalyticsRecentActivity(
            label="CRM lead",
            detail=title,
            occurred_at=occurred_at,
            href="/dashboard/crm",
        )
        for _lead_id, title, occurred_at in lead_rows
    )
    activity.extend(
        AnalyticsRecentActivity(
            label="Quote",
            detail=title,
            occurred_at=occurred_at,
            href=f"/dashboard/quotes/{quote_id}",
        )
        for quote_id, title, occurred_at in quote_rows
    )
    return sorted(activity, key=lambda item: item.occurred_at, reverse=True)[:8]


def _bucket(key: Any, count: Any) -> AnalyticsBucket:
    return AnalyticsBucket(
        key=_key(key),
        label=_label(key),
        count=int(count or 0),
    )


def _key(value: Any) -> str:
    return str(getattr(value, "value", value))


def _label(value: Any) -> str:
    return _key(value).replace("_", " ").title()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)
