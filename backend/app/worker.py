import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import MailboxConnection
from app.services.email_sync import EmailSyncService

logger = structlog.get_logger()


async def run() -> None:
    configure_logging()
    settings = get_settings()
    sync_service = EmailSyncService(settings)
    while True:
        try:
            async with SessionFactory() as session:
                mailboxes = (
                    await session.scalars(
                        select(MailboxConnection)
                        .where(
                            MailboxConnection.active.is_(True),
                            (
                                MailboxConnection.sync_lease_until.is_(None)
                                | (MailboxConnection.sync_lease_until < datetime.now(UTC))
                            ),
                        )
                        .with_for_update(skip_locked=True)
                        .limit(10)
                    )
                ).all()
                for mailbox in mailboxes:
                    mailbox.sync_lease_until = datetime.now(UTC) + timedelta(minutes=5)
                await session.commit()
                for mailbox in mailboxes:
                    try:
                        report = await sync_service.sync_mailbox(session, mailbox)
                        if report.imported:
                            logger.info(
                                "mailbox_synced",
                                mailbox_id=str(mailbox.id),
                                imported=report.imported,
                                messages_fetched=report.messages_fetched,
                                duplicates_skipped=report.duplicates_skipped,
                            )
                    finally:
                        mailbox.sync_lease_until = None
                        await session.commit()
        except Exception:
            logger.exception("mail_worker_cycle_failed")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run())
