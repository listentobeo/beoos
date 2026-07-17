from datetime import UTC, datetime, time
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.domain.reports import (
    DailyReportActivityItem,
    DailyReportPreview,
    DailyReportSendResult,
    DailyReportSettings,
    DailyReportSettingsUpdate,
    DailyReportTotals,
    normalized_daily_report_settings,
)
from app.infrastructure.models import (
    Business,
    CRMLead,
    Direction,
    DraftStatus,
    EmailDraft,
    EmailMessage,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadStage,
    LeadTemperature,
    MailboxConnection,
    Quote,
    QuoteStatus,
    ThreadStatus,
)
from app.services.alerts import AlertService
from app.services.push_notifications import PushNotificationService

logger = structlog.get_logger()

OPEN_QUOTE_STATUSES = {
    QuoteStatus.draft,
    QuoteStatus.needs_approval,
    QuoteStatus.approved,
    QuoteStatus.sent,
}


class DailyReportService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._alerts = AlertService(settings)
        self._push = PushNotificationService(settings)

    async def settings_for_business(
        self,
        session: AsyncSession,
        business_id: UUID,
    ) -> DailyReportSettings:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        return normalized_daily_report_settings(
            business.settings,
            fallback_email=business.primary_email,
            fallback_timezone=business.timezone,
        )

    async def update_settings(
        self,
        session: AsyncSession,
        business_id: UUID,
        payload: DailyReportSettingsUpdate,
    ) -> DailyReportSettings:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        current = await self.settings_for_business(session, business_id)
        next_settings = current.model_copy(update=payload.model_dump()).model_dump(mode="json")
        settings_blob = dict(business.settings or {})
        settings_blob["daily_report"] = next_settings
        business.settings = settings_blob
        await session.commit()
        logger.info(
            "daily_report_settings_updated",
            business_id=str(business_id),
            enabled=payload.enabled,
            time=payload.time,
            timezone=payload.timezone,
            push_enabled=payload.push_enabled,
        )
        return normalized_daily_report_settings(
            business.settings,
            fallback_email=business.primary_email,
            fallback_timezone=business.timezone,
        )

    async def preview(
        self,
        session: AsyncSession,
        business_id: UUID,
        *,
        settings_override: DailyReportSettings | None = None,
    ) -> DailyReportPreview:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        report_settings = settings_override or await self.settings_for_business(
            session,
            business_id,
        )
        timezone = _safe_zone(report_settings.timezone or business.timezone)
        now_local = datetime.now(timezone)
        day_start_local = datetime.combine(now_local.date(), time.min, tzinfo=timezone)
        day_start = day_start_local.astimezone(UTC)
        day_end = now_local.astimezone(UTC)
        recipient = str(report_settings.email or business.primary_email)

        totals = DailyReportTotals(
            inbound_messages=await self._message_count(
                session,
                business_id,
                day_start,
                day_end,
                EmailMessage.direction == Direction.inbound,
            ),
            unread_messages=int(
                await session.scalar(
                    select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
                        EmailThread.business_id == business_id
                    )
                )
                or 0
            ),
            whatsapp_messages=await self._message_count(
                session,
                business_id,
                day_start,
                day_end,
                MailboxConnection.provider == "whatsapp",
            ),
            needs_approval=await self._count(
                session,
                EmailThread.id,
                EmailThread.business_id == business_id,
                EmailThread.status == ThreadStatus.needs_approval,
            ),
            leads_created=await self._count(
                session,
                CRMLead.id,
                CRMLead.business_id == business_id,
                CRMLead.created_at >= day_start,
                CRMLead.created_at <= day_end,
            ),
            hot_leads=await self._count(
                session,
                CRMLead.id,
                CRMLead.business_id == business_id,
                CRMLead.temperature == LeadTemperature.hot,
                CRMLead.stage.not_in([LeadStage.won, LeadStage.lost]),
            ),
            quotes_created=await self._count(
                session,
                Quote.id,
                Quote.business_id == business_id,
                Quote.created_at >= day_start,
                Quote.created_at <= day_end,
            ),
            quotes_accepted=await self._count(
                session,
                Quote.id,
                Quote.business_id == business_id,
                Quote.status == QuoteStatus.accepted,
                Quote.accepted_at >= day_start,
                Quote.accepted_at <= day_end,
            ),
            followups_due=await self._count(
                session,
                FollowUpTask.id,
                FollowUpTask.business_id == business_id,
                FollowUpTask.status == FollowUpStatus.scheduled,
                FollowUpTask.scheduled_for <= day_end,
            ),
            pending_drafts=await self._pending_drafts(session, business_id),
            open_quote_value=await self._sum_decimal(
                session,
                select(func.coalesce(func.sum(Quote.total), 0)).where(
                    Quote.business_id == business_id,
                    Quote.status.in_(OPEN_QUOTE_STATUSES),
                ),
            ),
            accepted_quote_value=await self._sum_decimal(
                session,
                select(func.coalesce(func.sum(Quote.total), 0)).where(
                    Quote.business_id == business_id,
                    Quote.status == QuoteStatus.accepted,
                ),
            ),
        )
        highlights = _highlights(totals)
        action_items = _action_items(totals)
        subject = f"BeoOS daily report for {business.name} — {now_local:%b %d, %Y}"
        return DailyReportPreview(
            business_id=str(business.id),
            business_name=business.name,
            report_date=now_local.date().isoformat(),
            timezone=str(timezone.key if hasattr(timezone, "key") else timezone),
            recipient=recipient,
            subject=subject,
            totals=totals,
            highlights=highlights,
            action_items=action_items,
            recent_activity=await self._recent_activity(session, business_id),
        )

    async def send(
        self,
        session: AsyncSession,
        business_id: UUID,
        *,
        mark_sent: bool = False,
    ) -> DailyReportSendResult:
        business = await session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")
        report_settings = await self.settings_for_business(session, business_id)
        preview = await self.preview(session, business_id, settings_override=report_settings)
        body = _email_text(preview)
        email_sent = await self._alerts.send_daily_report_email(
            recipient=preview.recipient,
            subject=preview.subject,
            text=body,
        )
        push_sent = 0
        if report_settings.push_enabled:
            push_sent = await self._push.send_new_inbox_message(
                session,
                business_id=business.id,
                thread_id=business.id,
                title="BeoOS daily business report",
                body=f"{business.name}: {preview.totals.inbound_messages} new messages, "
                f"{preview.totals.needs_approval} approvals, "
                f"{preview.totals.leads_created} new leads.",
                channel="daily_report",
                url_path="/dashboard/analytics",
            )

        if mark_sent and (email_sent or push_sent):
            settings_blob = dict(business.settings or {})
            current = dict(settings_blob.get("daily_report") or {})
            current["last_sent_on"] = preview.report_date
            current["last_sent_at"] = datetime.now(UTC).isoformat()
            settings_blob["daily_report"] = current
            business.settings = settings_blob
            await session.commit()

        message = "Daily report sent."
        if not email_sent and not push_sent:
            message = "Report generated, but no email or push provider is configured/enabled."
        elif not email_sent:
            message = "Report generated. Push sent, but Resend email is not configured."
        return DailyReportSendResult(
            success=email_sent or push_sent,
            email_sent=email_sent,
            push_sent=push_sent,
            recipient=preview.recipient,
            subject=preview.subject,
            message=message,
            preview=preview,
        )

    async def _count(
        self,
        session: AsyncSession,
        column: object,
        *conditions: ColumnElement[bool],
    ) -> int:
        value = await session.scalar(select(func.count(column)).where(*conditions))
        return int(value or 0)

    async def _message_count(
        self,
        session: AsyncSession,
        business_id: UUID,
        since: datetime,
        until: datetime,
        *conditions: ColumnElement[bool],
    ) -> int:
        value = await session.scalar(
            select(func.count(EmailMessage.id))
            .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
            .join(MailboxConnection, MailboxConnection.id == EmailMessage.mailbox_id)
            .where(
                EmailThread.business_id == business_id,
                EmailMessage.sent_at >= since,
                EmailMessage.sent_at <= until,
                *conditions,
            )
        )
        return int(value or 0)

    async def _pending_drafts(self, session: AsyncSession, business_id: UUID) -> int:
        value = await session.scalar(
            select(func.count(EmailDraft.id))
            .join(EmailThread, EmailThread.id == EmailDraft.thread_id)
            .where(
                EmailThread.business_id == business_id,
                EmailDraft.status == DraftStatus.pending,
            )
        )
        return int(value or 0)

    async def _sum_decimal(self, session: AsyncSession, statement: object) -> Decimal:
        value = await session.scalar(statement)
        return Decimal(str(value or 0))

    async def _recent_activity(
        self,
        session: AsyncSession,
        business_id: UUID,
    ) -> list[DailyReportActivityItem]:
        rows = (
            await session.execute(
                select(EmailThread.id, EmailThread.subject, EmailThread.latest_message_at)
                .where(EmailThread.business_id == business_id)
                .order_by(EmailThread.latest_message_at.desc())
                .limit(6)
            )
        ).all()
        return [
            DailyReportActivityItem(
                label="Inbox",
                detail=subject,
                occurred_at=occurred_at,
                href=f"/dashboard/inbox/{thread_id}",
            )
            for thread_id, subject, occurred_at in rows
        ]


def _safe_zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Africa/Lagos")


def _highlights(totals: DailyReportTotals) -> list[str]:
    highlights = [
        f"{totals.inbound_messages} inbound message(s) came in today.",
        f"{totals.leads_created} new CRM lead(s) were created.",
        f"{totals.quotes_created} quote(s) were created today.",
    ]
    if totals.whatsapp_messages:
        highlights.append(f"{totals.whatsapp_messages} WhatsApp message(s) entered the inbox.")
    if totals.quotes_accepted:
        highlights.append(f"{totals.quotes_accepted} quote(s) were accepted.")
    return highlights


def _action_items(totals: DailyReportTotals) -> list[str]:
    items: list[str] = []
    if totals.needs_approval:
        items.append(f"Review {totals.needs_approval} conversation(s) waiting for approval.")
    if totals.pending_drafts:
        items.append(f"Approve, edit, or discard {totals.pending_drafts} AI draft(s).")
    if totals.followups_due:
        items.append(f"Handle {totals.followups_due} due follow-up task(s).")
    if totals.hot_leads:
        items.append(f"Prioritize {totals.hot_leads} hot open lead(s).")
    if not items:
        items.append("No urgent action is pending. Keep monitoring new inbox activity.")
    return items


def _email_text(preview: DailyReportPreview) -> str:
    totals = preview.totals
    highlights = "\n".join(f"- {item}" for item in preview.highlights)
    actions = "\n".join(f"- {item}" for item in preview.action_items)
    activity = "\n".join(
        f"- {item.label}: {item.detail}" for item in preview.recent_activity[:6]
    ) or "- No recent activity yet."
    return (
        f"{preview.subject}\n\n"
        f"Business: {preview.business_name}\n"
        f"Date: {preview.report_date} ({preview.timezone})\n\n"
        "Snapshot\n"
        f"- Inbound messages: {totals.inbound_messages}\n"
        f"- Unread messages: {totals.unread_messages}\n"
        f"- WhatsApp messages: {totals.whatsapp_messages}\n"
        f"- Needs approval: {totals.needs_approval}\n"
        f"- New leads: {totals.leads_created}\n"
        f"- Hot leads: {totals.hot_leads}\n"
        f"- Quotes created: {totals.quotes_created}\n"
        f"- Quotes accepted: {totals.quotes_accepted}\n"
        f"- Follow-ups due: {totals.followups_due}\n"
        f"- Pending drafts: {totals.pending_drafts}\n"
        f"- Open quote value: {totals.open_quote_value}\n"
        f"- Accepted quote value: {totals.accepted_quote_value}\n\n"
        f"Highlights\n{highlights}\n\n"
        f"Recommended actions\n{actions}\n\n"
        f"Recent activity\n{activity}\n\n"
        "Open BeoOS to review the full dashboard."
    )
