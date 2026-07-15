import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import (
    AuditLog,
    Business,
    Contact,
    CRMLead,
    Direction,
    EmailDraft,
    EmailMessage,
    EmailThread,
    FollowUpStatus,
    FollowUpTask,
    LeadStage,
    MailboxConnection,
    ThreadStatus,
)
from app.services.approval_notifications import ApprovalNotificationService

logger = structlog.get_logger()

OPEN_STAGES = {
    LeadStage.new,
    LeadStage.contacted,
    LeadStage.qualified,
    LeadStage.quote_needed,
    LeadStage.quoted,
    LeadStage.deposit_pending,
}


class FollowUpScheduler:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._notifications = ApprovalNotificationService(settings)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self._settings.follow_up_scheduler_enabled:
            logger.info("follow_up_scheduler_disabled")
            return
        if self.running:
            return
        self._task = asyncio.create_task(self.run_forever(), name="beoos-follow-up-scheduler")
        logger.info(
            "follow_up_scheduler_started",
            interval_seconds=self._settings.follow_up_scheduler_interval_seconds,
            batch_size=self._settings.follow_up_scheduler_batch_size,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        logger.info("follow_up_scheduler_stopped")

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("follow_up_scheduler_cycle_failed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(10, self._settings.follow_up_scheduler_interval_seconds),
                )
            except TimeoutError:
                pass

    async def run_once(self) -> int:
        processed = 0
        async with SessionFactory() as session:
            now = datetime.now(UTC)
            tasks = (
                await session.scalars(
                    select(FollowUpTask)
                    .where(
                        FollowUpTask.status == FollowUpStatus.scheduled,
                        FollowUpTask.scheduled_for <= now,
                    )
                    .order_by(FollowUpTask.scheduled_for.asc())
                    .with_for_update(skip_locked=True)
                    .limit(max(1, self._settings.follow_up_scheduler_batch_size))
                )
            ).all()
            if not tasks:
                logger.debug("follow_up_scheduler_no_due_tasks")
                return 0

            logger.info("follow_up_scheduler_due_tasks", tasks=len(tasks))
            for task in tasks:
                try:
                    await self._process_task(session, task)
                    processed += 1
                except Exception as exc:
                    task.status = FollowUpStatus.failed
                    task.error = f"{exc.__class__.__name__}: {str(exc)[:500]}"
                    task.completed_at = datetime.now(UTC)
                    await session.commit()
                    logger.exception(
                        "follow_up_task_failed",
                        task_id=str(task.id),
                        business_id=str(task.business_id),
                        lead_id=str(task.lead_id),
                    )
        return processed

    async def _process_task(self, session: AsyncSession, task: FollowUpTask) -> None:
        lead = await session.get(CRMLead, task.lead_id)
        if lead is None or lead.business_id != task.business_id:
            await self._skip(session, task, "Lead no longer exists")
            return
        if lead.stage not in OPEN_STAGES:
            await self._skip(session, task, f"Lead is already {lead.stage.value}")
            return
        if lead.thread_id is None:
            await self._skip(session, task, "Lead has no conversation thread")
            return
        thread = await session.get(EmailThread, lead.thread_id)
        if thread is None or thread.business_id != task.business_id:
            await self._skip(session, task, "Thread no longer exists")
            return
        business = await session.get(Business, task.business_id)
        if business is None:
            await self._skip(session, task, "Business no longer exists")
            return

        latest_inbound = await self._latest_inbound_message(session, thread.id)
        if latest_inbound is None:
            await self._skip(session, task, "No inbound message to reply to")
            return
        if latest_inbound.sent_at and latest_inbound.sent_at > task.created_at:
            await self._skip(session, task, "Client replied after follow-up was scheduled")
            return

        contact = await session.get(Contact, lead.contact_id) if lead.contact_id else None
        mailbox = await session.get(MailboxConnection, latest_inbound.mailbox_id)
        subject = _reply_subject(thread.subject)
        body_text = _follow_up_body(
            business=business,
            lead=lead,
            contact=contact,
            step_number=task.step_number,
        )
        draft_type = "whatsapp_reply" if mailbox and mailbox.provider == "whatsapp" else "follow_up"
        draft = EmailDraft(
            thread_id=thread.id,
            source_message_id=latest_inbound.id,
            subject=subject,
            body_text=body_text,
            draft_type=draft_type,
            auto_send_eligible=False,
            policy_reasons=[
                "Scheduled follow-up created by BeoOS",
                "Follow-ups require approval before sending",
            ],
        )
        session.add(draft)
        thread.status = ThreadStatus.needs_approval
        task.status = FollowUpStatus.draft_created
        task.completed_at = datetime.now(UTC)
        task.subject = subject
        task.body_text = body_text
        lead.next_follow_up_at = await self._next_scheduled_for(session, lead.id, exclude_task=task)
        session.add(
            AuditLog(
                business_id=task.business_id,
                actor_id="system",
                action="follow_up.draft_created",
                resource_type="follow_up_task",
                resource_id=str(task.id),
                details={
                    "lead_id": str(lead.id),
                    "thread_id": str(thread.id),
                    "step_number": task.step_number,
                    "draft_type": draft_type,
                },
            )
        )
        await session.commit()
        logger.info(
            "follow_up_draft_created",
            task_id=str(task.id),
            business_id=str(task.business_id),
            lead_id=str(lead.id),
            thread_id=str(thread.id),
            draft_id=str(draft.id),
        )
        await self._notifications.notify_needs_approval(
            session,
            business_id=task.business_id,
            thread_id=thread.id,
            reason=f"Scheduled follow-up step {task.step_number} is ready to review",
        )
        await session.commit()

    async def _skip(self, session: AsyncSession, task: FollowUpTask, reason: str) -> None:
        task.status = FollowUpStatus.skipped
        task.error = reason
        task.completed_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "follow_up_task_skipped",
            task_id=str(task.id),
            business_id=str(task.business_id),
            lead_id=str(task.lead_id),
            reason=reason,
        )

    async def _latest_inbound_message(
        self,
        session: AsyncSession,
        thread_id: UUID,
    ) -> EmailMessage | None:
        value = await session.scalar(
            select(EmailMessage)
            .where(
                EmailMessage.thread_id == thread_id,
                EmailMessage.direction == Direction.inbound,
            )
            .order_by(EmailMessage.sent_at.desc())
            .limit(1)
        )
        return value if isinstance(value, EmailMessage) else None

    async def _next_scheduled_for(
        self,
        session: AsyncSession,
        lead_id: UUID,
        *,
        exclude_task: FollowUpTask,
    ) -> datetime | None:
        value = await session.scalar(
            select(func.min(FollowUpTask.scheduled_for)).where(
                FollowUpTask.lead_id == lead_id,
                FollowUpTask.id != exclude_task.id,
                FollowUpTask.status == FollowUpStatus.scheduled,
            )
        )
        return value if isinstance(value, datetime) else None


def _reply_subject(subject: str) -> str:
    stripped = subject.strip() or "Follow-up"
    return stripped if stripped.lower().startswith("re:") else f"Re: {stripped}"


def _follow_up_body(
    *,
    business: Business,
    lead: CRMLead,
    contact: Contact | None,
    step_number: int,
) -> str:
    name = (contact.name or "").strip() if contact else ""
    greeting = f"Hi {name}," if name else "Hi,"
    service = f" about {lead.service}" if lead.service else ""
    deadline = f" before {lead.deadline}" if lead.deadline else ""
    budget = f" around {lead.budget}" if lead.budget else ""
    if step_number == 1:
        message = (
            f"Just checking in on your request{service}. "
            f"Would you still like us to help with this{deadline}{budget}?"
        )
    elif step_number == 2:
        message = (
            f"Following up again on your enquiry{service}. "
            "If you are still interested, send the key details and we can guide you "
            "on the next step."
        )
    else:
        message = (
            f"Last follow-up from {business.name} on this enquiry. "
            "If the timing is still good, reply here and we will pick it back up."
        )
    return f"{greeting}\n\n{message}\n\n{business.reply_signature}".strip()


def standard_follow_up_offsets(cadence: str) -> list[timedelta]:
    if cadence == "hot":
        return [timedelta(hours=6), timedelta(days=1), timedelta(days=3)]
    if cadence == "gentle":
        return [timedelta(days=2), timedelta(days=7), timedelta(days=14)]
    return [timedelta(days=1), timedelta(days=2), timedelta(days=7)]
