import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.mailbox_scheduler import MailboxAutoSyncScheduler


async def run() -> None:
    configure_logging()
    scheduler = MailboxAutoSyncScheduler(get_settings())
    await scheduler.run_forever()


if __name__ == "__main__":
    asyncio.run(run())
