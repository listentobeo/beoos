import asyncio
import json
from uuid import UUID

import structlog
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.models import Business, PushSubscription

logger = structlog.get_logger()


class PushNotificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._vapid_key: Vapid02 | str | None = None

    @property
    def configured(self) -> bool:
        return bool(self._settings.vapid_public_key and self._settings.vapid_private_key)

    async def send_new_inbox_message(
        self,
        session: AsyncSession,
        *,
        business_id: UUID,
        thread_id: UUID,
        title: str,
        body: str,
        channel: str,
        url_path: str | None = None,
    ) -> int:
        if not self.configured:
            logger.warning(
                "push_notification_not_configured",
                business_id=str(business_id),
                has_public_key=bool(self._settings.vapid_public_key),
                has_private_key=bool(self._settings.vapid_private_key),
            )
            return 0
        business = await session.get(Business, business_id)
        if business is None:
            logger.warning("push_notification_business_missing", business_id=str(business_id))
            return 0
        subscriptions = (
            await session.scalars(
                select(PushSubscription).where(
                    PushSubscription.business_id == business_id,
                    PushSubscription.active.is_(True),
                )
            )
        ).all()
        if not subscriptions:
            logger.info(
                "push_notification_no_active_subscriptions",
                business_id=str(business_id),
                thread_id=str(thread_id),
                channel=channel,
            )
            return 0

        payload = json.dumps(
            {
                "title": title[:120],
                "body": body[:220],
                "url": url_path or f"/dashboard/inbox/{thread_id}",
                "tag": f"beoos-{thread_id}",
                "business": business.name,
                "channel": channel,
            },
            ensure_ascii=False,
        )
        logger.info(
            "push_notification_sending",
            business_id=str(business_id),
            thread_id=str(thread_id),
            channel=channel,
            subscriptions=len(subscriptions),
        )
        sent = 0
        for subscription in subscriptions:
            if await self._send_one(subscription, payload):
                sent += 1
        logger.info(
            "push_notification_sent",
            business_id=str(business_id),
            thread_id=str(thread_id),
            channel=channel,
            sent=sent,
            subscriptions=len(subscriptions),
        )
        return sent

    async def _send_one(self, subscription: PushSubscription, payload: str) -> bool:
        info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        def send() -> None:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=self._private_key(),
                vapid_claims={"sub": self._settings.vapid_subject},
            )

        try:
            await asyncio.to_thread(send)
            return True
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {404, 410}:
                subscription.active = False
            logger.warning(
                "push_notification_failed",
                subscription_id=str(subscription.id),
                status_code=status_code,
                response_body=getattr(exc.response, "text", None),
            )
            return False
        except Exception:
            logger.exception(
                "push_notification_unexpected_failed",
                subscription_id=str(subscription.id),
            )
            return False

    def _private_key(self) -> Vapid02 | str:
        if self._vapid_key is not None:
            return self._vapid_key
        value = self._settings.vapid_private_key.strip()
        normalized = value.replace("\\n", "\n")
        if "-----BEGIN" in normalized:
            self._vapid_key = Vapid02.from_pem(normalized.encode())
            return self._vapid_key
        self._vapid_key = value
        return self._vapid_key
