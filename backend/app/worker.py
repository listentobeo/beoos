import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.durable_jobs import DurableJobWorker
from app.services.mailbox_scheduler import MailboxAutoSyncScheduler


async def run() -> None:
    configure_logging()
    settings = get_settings()
    scheduler = MailboxAutoSyncScheduler(settings)
    jobs = DurableJobWorker(settings)
    await asyncio.gather(scheduler.run_forever(), jobs.run_forever())


if __name__ == "__main__":
    asyncio.run(run())
