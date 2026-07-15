from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.models import Business, EmailThread
from app.services.alerts import AlertService
from app.services.push_notifications import PushNotificationService

logger = structlog.get_logger()


class ApprovalNotificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._push = PushNotificationService(settings)
        self._alerts = AlertService(settings)

    async def notify_needs_approval(
        self,
        session: AsyncSession,
        *,
        business_id: UUID,
        thread_id: UUID,
        reason: str,
    ) -> None:
        business = await session.get(Business, business_id)
        thread = await session.get(EmailThread, thread_id)
        if business is None or thread is None:
            logger.warning(
                "approval_notification_context_missing",
                business_id=str(business_id),
                thread_id=str(thread_id),
                has_business=business is not None,
                has_thread=thread is not None,
            )
            return

        body = f"{business.name}: {thread.subject}"
        try:
            await self._push.send_new_inbox_message(
                session,
                business_id=business.id,
                thread_id=thread.id,
                title="Approval needed in BeoOS",
                body=body,
                channel="approval",
                url_path="/dashboard/approvals",
            )
        except Exception:
            logger.exception(
                "approval_push_notification_failed",
                business_id=str(business.id),
                thread_id=str(thread.id),
            )

        try:
            await self._alerts.send_needs_approval_email(
                recipient=business.primary_email,
                business_name=business.name,
                thread_subject=thread.subject,
                reason=reason,
                url=f"{self._settings.frontend_url.rstrip('/')}/dashboard/approvals",
            )
        except Exception:
            logger.exception(
                "approval_email_notification_failed",
                business_id=str(business.id),
                thread_id=str(thread.id),
            )
