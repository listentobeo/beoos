from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_business_access
from app.domain.notifications import PushSubscriptionCreate, PushSubscriptionStatus
from app.infrastructure.database import get_session
from app.infrastructure.models import PushSubscription
from app.services.push_notifications import PushNotificationService

router = APIRouter(prefix="/businesses/{business_id}/notifications", tags=["notifications"])


@router.get("/push", response_model=PushSubscriptionStatus)
async def push_status(
    business_id: UUID,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PushSubscriptionStatus:
    exists = await session.scalar(
        select(PushSubscription.id).where(
            PushSubscription.business_id == business_id,
            PushSubscription.clerk_user_id == access.user_id,
            PushSubscription.active.is_(True),
        )
    )
    return PushSubscriptionStatus(
        enabled=exists is not None,
        vapid_public_key=settings.vapid_public_key,
    )


@router.post("/push", response_model=PushSubscriptionStatus)
async def subscribe_push(
    business_id: UUID,
    payload: PushSubscriptionCreate,
    access: BusinessAccess = Depends(require_business_access),
    user_agent: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PushSubscriptionStatus:
    subscription = await session.scalar(
        select(PushSubscription).where(
            PushSubscription.business_id == business_id,
            PushSubscription.clerk_user_id == access.user_id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    if subscription is None:
        subscription = PushSubscription(
            business_id=business_id,
            clerk_user_id=access.user_id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent or user_agent,
            active=True,
        )
        session.add(subscription)
    else:
        subscription.p256dh = payload.keys.p256dh
        subscription.auth = payload.keys.auth
        subscription.user_agent = payload.user_agent or user_agent
        subscription.active = True
    await session.commit()
    return PushSubscriptionStatus(enabled=True, vapid_public_key=settings.vapid_public_key)


@router.post("/push/test")
async def test_push_notification(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, int | bool]:
    sent = await PushNotificationService(settings).send_new_inbox_message(
        session,
        business_id=business_id,
        thread_id=uuid4(),
        title="BeoOS push test",
        body="Push notifications are active for this business on this device.",
        channel="test",
        url_path="/dashboard/inbox",
    )
    await session.commit()
    return {"success": sent > 0, "sent": sent}


@router.delete("/push", response_model=PushSubscriptionStatus)
async def unsubscribe_push(
    business_id: UUID,
    payload: PushSubscriptionCreate,
    access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PushSubscriptionStatus:
    subscription = await session.scalar(
        select(PushSubscription).where(
            PushSubscription.business_id == business_id,
            PushSubscription.clerk_user_id == access.user_id,
            PushSubscription.endpoint == payload.endpoint,
        )
    )
    if subscription is not None:
        subscription.active = False
        await session.commit()
    return PushSubscriptionStatus(enabled=False, vapid_public_key=settings.vapid_public_key)
