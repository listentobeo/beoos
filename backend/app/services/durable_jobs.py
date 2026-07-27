import asyncio
import socket
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import (
    Business,
    Contact,
    DurableJob,
    EmailMessage,
    EmailThread,
    PaymentTransaction,
    WhatsAppConnection,
    WhatsAppConnectionStatus,
    WhatsAppWebhookEvent,
)
from app.services.approval_notifications import ApprovalNotificationService
from app.services.beo_enquiry_workflow import record_commission_enquiry_workflow

logger = structlog.get_logger()

WEBSITE_AI_JOB = "website_form.ai_intake"
WHATSAPP_AI_JOB = "whatsapp.ai_intake"
MANUAL_AI_JOB = "manual.ai_intake"
PAYSTACK_RECONCILE_JOB = "paystack.transaction_reconcile"
WHATSAPP_CONTACTS_SYNC_JOB = "whatsapp.coexistence.contacts_sync"
WHATSAPP_HISTORY_SYNC_JOB = "whatsapp.coexistence.history_sync"
WHATSAPP_WEBHOOK_JOB = "whatsapp.webhook.process"


async def enqueue_job(
    session: AsyncSession,
    *,
    business_id: UUID,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    workflow_run_id: UUID | None = None,
    priority: int = 100,
    max_attempts: int = 5,
) -> DurableJob:
    existing = await session.scalar(
        select(DurableJob).where(
            DurableJob.business_id == business_id,
            DurableJob.job_type == job_type,
            DurableJob.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    job = DurableJob(
        business_id=business_id,
        job_type=job_type,
        workflow_run_id=workflow_run_id,
        payload=payload,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
        available_at=datetime.now(UTC),
    )
    session.add(job)
    await session.flush()
    return job


class DurableJobWorker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._worker_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:12]}"

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self._settings.durable_job_worker_enabled or self.running:
            return
        self._task = asyncio.create_task(self.run_forever(), name="beoos-durable-job-worker")
        logger.info("durable_job_worker_started", worker_id=self._worker_id)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("durable_job_cycle_failed", worker_id=self._worker_id)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(1, self._settings.durable_job_poll_interval_seconds),
                )
            except TimeoutError:
                pass

    async def run_once(self) -> int:
        job_ids = await self._claim()
        for job_id in job_ids:
            await self._process(job_id)
        return len(job_ids)

    async def _claim(self) -> list[UUID]:
        now = datetime.now(UTC)
        lease_expired = now - timedelta(seconds=max(30, self._settings.durable_job_lease_seconds))
        async with SessionFactory() as session:
            jobs = (
                await session.scalars(
                    select(DurableJob)
                    .where(
                        or_(
                            (
                                DurableJob.status.in_(("queued", "retry_scheduled"))
                                & (DurableJob.available_at <= now)
                            ),
                            (
                                (DurableJob.status == "running")
                                & (DurableJob.locked_at < lease_expired)
                            ),
                        )
                    )
                    .order_by(DurableJob.priority.asc(), DurableJob.available_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(max(1, self._settings.durable_job_batch_size))
                )
            ).all()
            for job in jobs:
                job.status = "running"
                job.locked_at = now
                job.locked_by = self._worker_id
                job.attempt_count += 1
            await session.commit()
            return [job.id for job in jobs]

    async def _process(self, job_id: UUID) -> None:
        async with SessionFactory() as session:
            job = await session.scalar(
                select(DurableJob).where(
                    DurableJob.id == job_id,
                    DurableJob.status == "running",
                    DurableJob.locked_by == self._worker_id,
                )
            )
            if job is None:
                return
            try:
                await self._dispatch(session, job)
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.locked_at = None
                job.locked_by = None
                job.last_error = None
                await session.commit()
                logger.info(
                    "durable_job_completed",
                    job_id=str(job.id),
                    business_id=str(job.business_id),
                    job_type=job.job_type,
                    attempt=job.attempt_count,
                )
            except Exception as exc:
                await session.rollback()
                job = await session.get(DurableJob, job_id)
                if job is None:
                    return
                job.last_error = _sanitized_error(exc)
                job.locked_at = None
                job.locked_by = None
                if job.attempt_count >= job.max_attempts:
                    job.status = "dead_letter"
                    if job.job_type == WHATSAPP_WEBHOOK_JOB:
                        event = await session.get(
                            WhatsAppWebhookEvent,
                            _uuid(job.payload.get("event_id")),
                        )
                        if event is not None:
                            event.status = "failed"
                            event.processing_error = job.last_error
                    if job.job_type in {
                        WHATSAPP_CONTACTS_SYNC_JOB,
                        WHATSAPP_HISTORY_SYNC_JOB,
                    }:
                        connection = await session.get(
                            WhatsAppConnection,
                            _uuid(job.payload.get("connection_id")),
                        )
                        if connection is not None:
                            if job.job_type == WHATSAPP_CONTACTS_SYNC_JOB:
                                connection.contacts_sync_status = "failed"
                            else:
                                connection.history_sync_status = "failed"
                            connection.connection_status = (
                                WhatsAppConnectionStatus.action_required
                            )
                            connection.last_error_code = "coexistence_sync_failed"
                            connection.last_error_message = job.last_error
                            from app.services.whatsapp_coexistence import (
                                update_business_whatsapp_from_connection,
                            )

                            await update_business_whatsapp_from_connection(
                                session,
                                connection,
                            )
                else:
                    job.status = "retry_scheduled"
                    job.available_at = datetime.now(UTC) + _backoff(job.attempt_count)
                await session.commit()
                logger.exception(
                    "durable_job_failed",
                    job_id=str(job.id),
                    business_id=str(job.business_id),
                    job_type=job.job_type,
                    status=job.status,
                    attempt=job.attempt_count,
                )

    async def _dispatch(self, session: AsyncSession, job: DurableJob) -> None:
        if job.job_type == WEBSITE_AI_JOB:
            await self._website_ai(session, job)
            return
        if job.job_type == WHATSAPP_AI_JOB:
            await self._whatsapp_ai(session, job)
            return
        if job.job_type == MANUAL_AI_JOB:
            await self._manual_ai(session, job)
            return
        if job.job_type == PAYSTACK_RECONCILE_JOB:
            await self._paystack_reconcile(session, job)
            return
        if job.job_type == WHATSAPP_CONTACTS_SYNC_JOB:
            await self._whatsapp_coexistence_sync(session, job, "smb_app_state_sync")
            return
        if job.job_type == WHATSAPP_HISTORY_SYNC_JOB:
            await self._whatsapp_coexistence_sync(session, job, "history")
            return
        if job.job_type == WHATSAPP_WEBHOOK_JOB:
            await self._whatsapp_webhook(session, job)
            return
        raise ValueError(f"Unsupported durable job type: {job.job_type}")

    async def _website_ai(self, session: AsyncSession, job: DurableJob) -> None:
        from app.api.forms import _run_ai_intake

        business, contact, thread, message = await _load_intake_records(session, job)
        await _run_ai_intake(session, self._settings, business, contact, thread, message)
        await session.flush()
        await record_commission_enquiry_workflow(
            session,
            self._settings,
            business=business,
            contact=contact,
            thread=thread,
            message=message,
            channel="website_form",
        )
        if thread.status.value == "needs_approval":
            await ApprovalNotificationService(self._settings).notify_needs_approval(
                session,
                business_id=business.id,
                thread_id=thread.id,
                reason="Website enquiry draft is waiting for review",
            )

    async def _whatsapp_ai(self, session: AsyncSession, job: DurableJob) -> None:
        from app.api.whatsapp import _run_whatsapp_ai_intake

        business, contact, thread, message = await _load_intake_records(session, job)
        await _run_whatsapp_ai_intake(session, self._settings, business, contact, thread, message)
        await session.flush()
        await record_commission_enquiry_workflow(
            session,
            self._settings,
            business=business,
            contact=contact,
            thread=thread,
            message=message,
            channel="whatsapp",
        )
        if thread.status.value == "needs_approval":
            await ApprovalNotificationService(self._settings).notify_needs_approval(
                session,
                business_id=business.id,
                thread_id=thread.id,
                reason="WhatsApp reply draft is waiting for review",
            )

    async def _manual_ai(self, session: AsyncSession, job: DurableJob) -> None:
        from app.api.forms import _run_ai_intake

        business, contact, thread, message = await _load_intake_records(session, job)
        await _run_ai_intake(session, self._settings, business, contact, thread, message)
        await session.flush()
        await record_commission_enquiry_workflow(
            session,
            self._settings,
            business=business,
            contact=contact,
            thread=thread,
            message=message,
            channel="manual",
        )
        if thread.status.value == "needs_approval":
            await ApprovalNotificationService(self._settings).notify_needs_approval(
                session,
                business_id=business.id,
                thread_id=thread.id,
                reason="Manual enquiry draft is waiting for review",
            )

    async def _paystack_reconcile(self, session: AsyncSession, job: DurableJob) -> None:
        from app.services.payments import apply_paystack_status
        from app.services.paystack import PaystackService

        transaction = await session.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.id == _uuid(job.payload.get("payment_transaction_id")),
                PaymentTransaction.business_id == job.business_id,
            )
        )
        if transaction is None:
            raise ValueError("Payment reconciliation references a missing transaction")
        if transaction.status == "confirmed":
            return
        data = await PaystackService(self._settings).verify_transaction(
            transaction.provider_reference
        )
        await apply_paystack_status(
            session,
            transaction,
            data,
            actor_id="system:paystack_reconciliation",
        )

    async def _whatsapp_coexistence_sync(
        self,
        session: AsyncSession,
        job: DurableJob,
        sync_type: Literal["smb_app_state_sync", "history"],
    ) -> None:
        from app.services.whatsapp_coexistence import execute_coexistence_sync_job

        if sync_type not in {"smb_app_state_sync", "history"}:
            raise ValueError("Unsupported WhatsApp coexistence synchronization type")
        await execute_coexistence_sync_job(
            session,
            self._settings,
            job,
            sync_type=sync_type,
        )

    async def _whatsapp_webhook(self, session: AsyncSession, job: DurableJob) -> None:
        from app.api.whatsapp import process_whatsapp_webhook_event

        await process_whatsapp_webhook_event(
            session,
            self._settings,
            event_id=_uuid(job.payload.get("event_id")),
            business_id=job.business_id,
        )


async def _load_intake_records(
    session: AsyncSession, job: DurableJob
) -> tuple[Business, Contact, EmailThread, EmailMessage]:
    business = await session.get(Business, job.business_id)
    contact = await session.scalar(
        select(Contact).where(
            Contact.id == _uuid(job.payload.get("contact_id")),
            Contact.business_id == job.business_id,
        )
    )
    thread = await session.scalar(
        select(EmailThread).where(
            EmailThread.id == _uuid(job.payload.get("thread_id")),
            EmailThread.business_id == job.business_id,
        )
    )
    message = await session.get(EmailMessage, _uuid(job.payload.get("message_id")))
    if (
        business is None
        or contact is None
        or thread is None
        or message is None
        or message.thread_id != thread.id
    ):
        raise ValueError("Durable intake job references missing or cross-tenant records")
    return business, contact, thread, message


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Durable job contains an invalid record reference") from exc


def _backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(900, 5 * (2 ** max(0, attempt - 1))))


def _sanitized_error(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {str(exc)[:500]}"
