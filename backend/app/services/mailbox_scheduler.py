import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from app.core.config import Settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import MailboxConnection
from app.services.email_sync import EmailSyncService

logger = structlog.get_logger()


class MailboxAutoSyncScheduler:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self._settings.mailbox_auto_sync_enabled:
            logger.info("mailbox_auto_sync_disabled")
            return
        if self.running:
            return
        self._task = asyncio.create_task(self.run_forever(), name="beoos-mailbox-auto-sync")
        logger.info(
            "mailbox_auto_sync_started",
            interval_seconds=self._settings.mailbox_auto_sync_interval_seconds,
            batch_size=self._settings.mailbox_auto_sync_batch_size,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        logger.info("mailbox_auto_sync_stopped")

    async def run_forever(self) -> None:
        service = EmailSyncService(self._settings)
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_once(service)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("mailbox_auto_sync_cycle_failed")
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=max(10, self._settings.mailbox_auto_sync_interval_seconds),
                    )
                except TimeoutError:
                    pass
        finally:
            await service.close()

    async def run_once(self, sync_service: EmailSyncService | None = None) -> int:
        owns_service = sync_service is None
        service = sync_service or EmailSyncService(self._settings)
        synced_count = 0
        try:
            async with SessionFactory() as session:
                now = datetime.now(UTC)
                lease_until = now + timedelta(
                    minutes=max(1, self._settings.mailbox_auto_sync_lease_minutes)
                )
                mailboxes = (
                    await session.scalars(
                        select(MailboxConnection)
                        .where(
                            MailboxConnection.active.is_(True),
                            MailboxConnection.provider.in_(["zoho", "gmail"]),
                            MailboxConnection.refresh_token_encrypted.is_not(None),
                            (
                                MailboxConnection.sync_lease_until.is_(None)
                                | (MailboxConnection.sync_lease_until < now)
                            ),
                        )
                        .with_for_update(skip_locked=True)
                        .limit(max(1, self._settings.mailbox_auto_sync_batch_size))
                    )
                ).all()
                for mailbox in mailboxes:
                    mailbox.sync_lease_until = lease_until
                await session.commit()

                if not mailboxes:
                    logger.debug("mailbox_auto_sync_no_mailboxes")
                    return 0

                logger.info("mailbox_auto_sync_cycle_started", mailboxes=len(mailboxes))
                for mailbox in mailboxes:
                    try:
                        report = await service.sync_mailbox(session, mailbox)
                        synced_count += 1
                        logger.info(
                            "mailbox_auto_sync_mailbox_finished",
                            mailbox_id=str(mailbox.id),
                            business_id=str(mailbox.business_id),
                            provider=mailbox.provider,
                            messages_fetched=report.messages_fetched,
                            messages_created=report.messages_created,
                            duplicates_skipped=report.duplicates_skipped,
                        )
                    except Exception:
                        logger.exception(
                            "mailbox_auto_sync_mailbox_failed",
                            mailbox_id=str(mailbox.id),
                            business_id=str(mailbox.business_id),
                            provider=mailbox.provider,
                        )
                    finally:
                        mailbox.sync_lease_until = None
                        await session.commit()
                logger.info("mailbox_auto_sync_cycle_finished", synced=synced_count)
                return synced_count
        finally:
            if owns_service:
                await service.close()
