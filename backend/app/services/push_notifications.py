import asyncio
import json
from uuid import UUID

import structlog
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.infrastructure.models import Business, PushSubscription

logger = structlog.get_logger()


class PushNotificationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

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
    ) -> None:
        if not self.configured:
            return
        business = await session.get(Business, business_id)
        if business is None:
            return
        subscriptions = (
            await session.scalars(
                select(PushSubscription).where(
                    PushSubscription.business_id == business_id,
                    PushSubscription.active.is_(True),
                )
            )
        ).all()
        if not subscriptions:
            return

        payload = json.dumps(
            {
                "title": title[:120],
                "body": body[:220],
                "url": f"/dashboard/inbox/{thread_id}",
                "tag": f"beoos-{thread_id}",
                "business": business.name,
                "channel": channel,
            },
            ensure_ascii=False,
        )
        for subscription in subscriptions:
            await self._send_one(subscription, payload)

    async def _send_one(self, subscription: PushSubscription, payload: str) -> None:
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
                vapid_private_key=self._settings.vapid_private_key,
                vapid_claims={"sub": self._settings.vapid_subject},
            )

        try:
            await asyncio.to_thread(send)
        except WebPushException as exc:
            status_code = getattr(exc.response, "status_code", None)
            if status_code in {404, 410}:
                subscription.active = False
            logger.warning(
                "push_notification_failed",
                subscription_id=str(subscription.id),
                status_code=status_code,
            )
        except Exception:
            logger.exception(
                "push_notification_unexpected_failed",
                subscription_id=str(subscription.id),
            )
