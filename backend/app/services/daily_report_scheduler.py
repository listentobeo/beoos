import asyncio
from contextlib import suppress
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select

from app.core.config import Settings
from app.domain.reports import normalized_daily_report_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import Business
from app.services.daily_reports import DailyReportService

logger = structlog.get_logger()


class DailyReportScheduler:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._reports = DailyReportService(settings)

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if not self._settings.daily_report_scheduler_enabled:
            logger.info("daily_report_scheduler_disabled")
            return
        if self.running:
            return
        self._task = asyncio.create_task(self.run_forever(), name="beoos-daily-report-scheduler")
        logger.info(
            "daily_report_scheduler_started",
            interval_seconds=self._settings.daily_report_scheduler_interval_seconds,
            batch_size=self._settings.daily_report_scheduler_batch_size,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        logger.info("daily_report_scheduler_stopped")

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("daily_report_scheduler_cycle_failed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=max(60, self._settings.daily_report_scheduler_interval_seconds),
                )
            except TimeoutError:
                pass

    async def run_once(self) -> int:
        processed = 0
        async with SessionFactory() as session:
            businesses = (
                await session.scalars(
                    select(Business)
                    .order_by(Business.updated_at.desc())
                    .limit(max(1, self._settings.daily_report_scheduler_batch_size))
                )
            ).all()
            for business in businesses:
                report_settings = normalized_daily_report_settings(
                    business.settings,
                    fallback_email=business.primary_email,
                    fallback_timezone=business.timezone,
                )
                if not report_settings.enabled:
                    continue
                timezone = _safe_zone(report_settings.timezone)
                now_local = datetime.now(timezone)
                today = now_local.date().isoformat()
                if report_settings.last_sent_on == today:
                    continue
                if now_local.strftime("%H:%M") < report_settings.time:
                    continue
                result = await self._reports.send(session, business.id, mark_sent=True)
                processed += 1
                logger.info(
                    "daily_report_scheduler_sent",
                    business_id=str(business.id),
                    email_sent=result.email_sent,
                    push_sent=result.push_sent,
                    recipient=result.recipient,
                    success=result.success,
                )
        if not processed:
            logger.debug("daily_report_scheduler_no_due_reports")
        return processed


def _safe_zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Africa/Lagos")
