from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings, get_settings
from app.core.security import AuthenticatedUser, BusinessAccess, require_admin, require_user
from app.domain.business import (
    BusinessAIPolicy,
    BusinessWhatsAppSettings,
    default_business_settings,
    ensure_website_form_key,
    normalized_ai_policy,
    normalized_whatsapp_settings,
    website_form_key,
)
from app.domain.email import InboxStats, MailboxStatus, ThreadListItem
from app.domain.notifications import PushSubscriptionStatus
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    Business,
    BusinessMember,
    Contact,
    EmailMessage,
    EmailThread,
    MailboxConnection,
    PushSubscription,
    Role,
    ThreadCategory,
    ThreadStatus,
)
from app.services.crypto import SecretCipher

router = APIRouter(prefix="/businesses", tags=["businesses"])
logger = structlog.get_logger()


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    primary_email: EmailStr
    whatsapp_number: str = Field(min_length=8, max_length=32)
    reply_signature: str = Field(min_length=2, max_length=500)


class BusinessUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    primary_email: EmailStr
    whatsapp_number: str = Field(min_length=8, max_length=32)
    reply_signature: str = Field(min_length=2, max_length=500)
    timezone: str = Field(default="Africa/Lagos", min_length=2, max_length=64)


class BusinessView(BaseModel):
    id: str
    slug: str
    name: str
    primary_email: EmailStr
    whatsapp_number: str
    reply_signature: str
    timezone: str
    role: str
    ai_policy: BusinessAIPolicy
    whatsapp_connection: BusinessWhatsAppSettings
    website_form_key: str


class WhatsAppEmbeddedConfig(BaseModel):
    app_id: str
    config_id: str
    graph_version: str
    enabled: bool


class WhatsAppEmbeddedSignupPayload(BaseModel):
    code: str = Field(default="", max_length=2048)
    access_token: str = Field(default="", max_length=4096)
    waba_id: str = Field(default="", max_length=120)
    phone_number_id: str = Field(default="", max_length=120)
    display_phone_number: str = Field(default="", max_length=40)
    redirect_uri: str = Field(default="", max_length=2000)
    meta_payload: dict[str, Any] = Field(default_factory=dict)


class WhatsAppEmbeddedSignupResult(BaseModel):
    success: bool
    business_id: str
    phone_number_id: str
    business_account_id: str
    display_phone_number: str
    connected_via: str


class DashboardSummary(BaseModel):
    business: BusinessView
    inbox_stats: InboxStats
    threads: list[ThreadListItem]
    mailbox: MailboxStatus
    zoho_mailbox: MailboxStatus
    gmail_mailbox: MailboxStatus
    push_status: PushSubscriptionStatus


@router.get("", response_model=list[BusinessView])
async def list_businesses(
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[BusinessView]:
    rows = (
        await session.execute(
            select(Business, BusinessMember.role)
            .join(BusinessMember, BusinessMember.business_id == Business.id)
            .where(BusinessMember.clerk_user_id == user.user_id)
            .order_by(Business.name)
        )
    ).all()
    changed = False
    for business, _role in rows:
        settings, created = ensure_website_form_key(business.settings)
        if created:
            business.settings = settings
            changed = True
    if changed:
        await session.commit()
    return [
        BusinessView(
            id=str(business.id),
            slug=business.slug,
            name=business.name,
            primary_email=business.primary_email,
            whatsapp_number=business.whatsapp_number,
            reply_signature=business.reply_signature,
            timezone=business.timezone,
            role=role.value,
            ai_policy=normalized_ai_policy(business.settings),
            whatsapp_connection=normalized_whatsapp_settings(business.settings),
            website_form_key=website_form_key(business.settings),
        )
        for business, role in rows
    ]


@router.get("/{business_id}/dashboard", response_model=DashboardSummary)
async def dashboard_summary(
    business_id: UUID,
    search: str | None = None,
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> DashboardSummary:
    member = await session.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.clerk_user_id == user.user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="You do not have access to this business")
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    mailbox_query = select(MailboxConnection).where(
        MailboxConnection.business_id == business_id,
        MailboxConnection.provider.in_(["zoho", "gmail"]),
    )
    mailbox = await session.scalar(
        mailbox_query.order_by(MailboxConnection.updated_at.desc()).limit(1)
    )
    zoho_mailbox = await _mailbox_for_provider(session, business_id, "zoho")
    gmail_mailbox = await _mailbox_for_provider(session, business_id, "gmail")

    return DashboardSummary(
        business=_business_view(business, member.role.value),
        inbox_stats=await _inbox_stats(session, business_id),
        threads=await _recent_threads(session, business_id, search=search),
        mailbox=await _mailbox_status(session, business_id, mailbox, settings=settings),
        zoho_mailbox=await _mailbox_status(session, business_id, zoho_mailbox, settings=settings),
        gmail_mailbox=await _mailbox_status(session, business_id, gmail_mailbox, settings=settings),
        push_status=await _push_status(
            session,
            business_id=business_id,
            user_id=user.user_id,
            settings=settings,
        ),
    )


@router.post("", status_code=201)
async def create_business(
    payload: BusinessCreate,
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if await session.scalar(select(Business.id).where(Business.slug == payload.slug)):
        raise HTTPException(status_code=409, detail="Business slug already exists")
    business = Business(
        **payload.model_dump(mode="json"),
        settings=default_business_settings(),
    )
    session.add(business)
    await session.flush()
    session.add(
        BusinessMember(
            business_id=business.id,
            clerk_user_id=user.user_id,
            role=Role.owner,
        )
    )
    await session.commit()
    return {"id": str(business.id), "slug": business.slug, "name": business.name}


@router.patch("/{business_id}", response_model=BusinessView)
async def update_business_profile(
    business_id: UUID,
    payload: BusinessUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> BusinessView:
    return await _update_business_profile(
        business_id=business_id,
        payload=payload,
        role=access.role.value,
        session=session,
    )


@router.patch("/{business_id}/profile", response_model=BusinessView)
async def update_business_profile_explicit(
    business_id: UUID,
    payload: BusinessUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> BusinessView:
    return await _update_business_profile(
        business_id=business_id,
        payload=payload,
        role=access.role.value,
        session=session,
    )


async def _update_business_profile(
    *,
    business_id: UUID,
    payload: BusinessUpdate,
    role: str,
    session: AsyncSession,
) -> BusinessView:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    business.name = payload.name
    business.primary_email = str(payload.primary_email)
    business.whatsapp_number = payload.whatsapp_number
    business.reply_signature = payload.reply_signature
    business.timezone = payload.timezone
    await session.commit()
    return BusinessView(
        id=str(business.id),
        slug=business.slug,
        name=business.name,
        primary_email=business.primary_email,
        whatsapp_number=business.whatsapp_number,
        reply_signature=business.reply_signature,
        timezone=business.timezone,
        role=role,
        ai_policy=normalized_ai_policy(business.settings),
        whatsapp_connection=normalized_whatsapp_settings(business.settings),
        website_form_key=website_form_key(business.settings),
    )


@router.patch("/{business_id}/policy", response_model=BusinessView)
async def update_business_policy(
    business_id: UUID,
    payload: BusinessAIPolicy,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> BusinessView:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    settings = dict(business.settings or {})
    settings["ai_policy"] = payload.model_dump()
    business.settings = settings
    await session.commit()
    return BusinessView(
        id=str(business.id),
        slug=business.slug,
        name=business.name,
        primary_email=business.primary_email,
        whatsapp_number=business.whatsapp_number,
        reply_signature=business.reply_signature,
        timezone=business.timezone,
        role=access.role.value,
        ai_policy=payload,
        whatsapp_connection=normalized_whatsapp_settings(settings),
        website_form_key=website_form_key(settings),
    )


@router.patch("/{business_id}/whatsapp", response_model=BusinessView)
async def update_business_whatsapp(
    business_id: UUID,
    payload: BusinessWhatsAppSettings,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> BusinessView:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    settings = dict(business.settings or {})
    current_whatsapp = settings.get("whatsapp")
    if not isinstance(current_whatsapp, dict):
        current_whatsapp = {}
    next_whatsapp = payload.model_dump()
    for secret_field in ("access_token_encrypted", "token_expires_at", "meta_payload"):
        if current_whatsapp.get(secret_field):
            next_whatsapp[secret_field] = current_whatsapp[secret_field]
    if current_whatsapp.get("connected_via") == "embedded_signup":
        next_whatsapp["connected_via"] = current_whatsapp["connected_via"]
        next_whatsapp["connected_at"] = current_whatsapp.get("connected_at", payload.connected_at)
    settings["whatsapp"] = next_whatsapp
    business.settings = settings
    await session.commit()
    return BusinessView(
        id=str(business.id),
        slug=business.slug,
        name=business.name,
        primary_email=business.primary_email,
        whatsapp_number=business.whatsapp_number,
        reply_signature=business.reply_signature,
        timezone=business.timezone,
        role=access.role.value,
        ai_policy=normalized_ai_policy(settings),
        whatsapp_connection=normalized_whatsapp_settings(settings),
        website_form_key=website_form_key(settings),
    )


@router.get("/{business_id}/whatsapp/embedded-config", response_model=WhatsAppEmbeddedConfig)
async def whatsapp_embedded_config(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> WhatsAppEmbeddedConfig:
    del business_id
    return WhatsAppEmbeddedConfig(
        app_id=settings.meta_app_id,
        config_id=settings.meta_whatsapp_config_id,
        graph_version=settings.whatsapp_graph_base_url.rstrip("/").split("/")[-1] or "v20.0",
        enabled=bool(
            settings.meta_app_id
            and settings.meta_whatsapp_config_id
            and settings.meta_app_secret
        ),
    )


@router.post("/{business_id}/whatsapp/embedded-signup", response_model=WhatsAppEmbeddedSignupResult)
async def complete_whatsapp_embedded_signup(
    business_id: UUID,
    payload: WhatsAppEmbeddedSignupPayload,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppEmbeddedSignupResult:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise HTTPException(status_code=409, detail="Meta app credentials are not configured")

    if payload.code:
        try:
            token_response = await _exchange_meta_code(
                settings,
                payload.code,
                redirect_uri=payload.redirect_uri,
            )
        except HTTPException as code_error:
            if not payload.access_token:
                raise
            logger.info(
                "meta_code_exchange_failed_trying_sdk_token",
                business_id=str(business.id),
            )
            try:
                token_response = await _exchange_meta_access_token(settings, payload.access_token)
            except HTTPException as token_error:
                raise code_error from token_error
    elif payload.access_token:
        logger.info("meta_embedded_signup_using_sdk_token", business_id=str(business.id))
        token_response = await _exchange_meta_access_token(settings, payload.access_token)
    else:
        raise HTTPException(status_code=422, detail="Meta did not return a code or access token")
    access_token = str(token_response.get("access_token") or "")
    if not access_token:
        logger.warning("whatsapp_embedded_signup_missing_token", business_id=str(business.id))
        raise HTTPException(status_code=400, detail="Meta did not return an access token")

    resolved = await _resolve_whatsapp_assets(
        settings=settings,
        access_token=access_token,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        display_phone_number=payload.display_phone_number,
    )
    if not resolved["phone_number_id"] or not resolved["business_account_id"]:
        logger.warning(
            "whatsapp_embedded_signup_incomplete_assets",
            business_id=str(business.id),
            payload=payload.model_dump(exclude={"code"}),
            resolved=resolved,
        )
        raise HTTPException(
            status_code=400,
            detail="Meta did not return a WhatsApp Business Account and phone number",
        )

    settings_blob = dict(business.settings or {})
    current_whatsapp = settings_blob.get("whatsapp")
    if not isinstance(current_whatsapp, dict):
        current_whatsapp = {}
    cipher = SecretCipher(settings.secret_encryption_key)
    token_expires_at = ""
    if token_response.get("expires_in"):
        token_expires_at = (
            datetime.now(UTC) + timedelta(seconds=int(token_response["expires_in"]))
        ).isoformat()
    current_whatsapp.update(
        {
            "enabled": True,
            "phone_number_id": resolved["phone_number_id"],
            "business_account_id": resolved["business_account_id"],
            "display_phone_number": resolved["display_phone_number"],
            "connected_via": "embedded_signup",
            "connected_at": datetime.now(UTC).isoformat(),
            "access_token_encrypted": cipher.encrypt(access_token),
            "token_expires_at": token_expires_at,
            "meta_payload": payload.meta_payload,
        }
    )
    settings_blob["whatsapp"] = current_whatsapp
    business.settings = settings_blob
    if resolved["display_phone_number"]:
        business.whatsapp_number = resolved["display_phone_number"]

    await session.commit()
    logger.info(
        "whatsapp_embedded_signup_connected",
        business_id=str(business.id),
        user_id=access.user_id,
        phone_number_id=resolved["phone_number_id"],
        business_account_id=resolved["business_account_id"],
    )
    return WhatsAppEmbeddedSignupResult(
        success=True,
        business_id=str(business.id),
        phone_number_id=resolved["phone_number_id"],
        business_account_id=resolved["business_account_id"],
        display_phone_number=resolved["display_phone_number"],
        connected_via="embedded_signup",
    )


async def _exchange_meta_code(
    settings: Settings,
    code: str,
    *,
    redirect_uri: str = "",
) -> dict[str, Any]:
    try:
        return await _exchange_meta_code_once(settings, code)
    except HTTPException as first_error:
        if not redirect_uri:
            raise
        logger.info("meta_code_exchange_retrying_with_redirect_uri")
        try:
            return await _exchange_meta_code_once(settings, code, redirect_uri=redirect_uri)
        except HTTPException as retry_error:
            raise first_error from retry_error


async def _exchange_meta_code_once(
    settings: Settings,
    code: str,
    *,
    redirect_uri: str = "",
) -> dict[str, Any]:
    params = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "code": code,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.post(
            f"{settings.whatsapp_graph_base_url.rstrip('/')}/oauth/access_token",
            data=params,
        )
    if response.is_error:
        body = response.text[:500]
        logger.warning(
            "meta_code_exchange_failed",
            status_code=response.status_code,
            body=body,
            used_redirect_uri=bool(redirect_uri),
        )
        raise HTTPException(status_code=400, detail="Could not exchange Meta authorization code")
    data = response.json()
    return data if isinstance(data, dict) else {}


async def _exchange_meta_access_token(
    settings: Settings,
    access_token: str,
) -> dict[str, Any]:
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "fb_exchange_token": access_token,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.post(
            f"{settings.whatsapp_graph_base_url.rstrip('/')}/oauth/access_token",
            data=params,
        )
    if response.is_error:
        logger.warning(
            "meta_sdk_token_exchange_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        raise HTTPException(status_code=400, detail="Could not exchange Meta SDK access token")
    data = response.json()
    return data if isinstance(data, dict) else {}


async def _resolve_whatsapp_assets(
    *,
    settings: Settings,
    access_token: str,
    waba_id: str,
    phone_number_id: str,
    display_phone_number: str,
) -> dict[str, str]:
    resolved = {
        "business_account_id": waba_id,
        "phone_number_id": phone_number_id,
        "display_phone_number": display_phone_number,
    }
    if resolved["phone_number_id"] and resolved["business_account_id"]:
        return resolved

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        if resolved["business_account_id"]:
            response = await client.get(
                f"{settings.whatsapp_graph_base_url.rstrip('/')}/{resolved['business_account_id']}/phone_numbers",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "id,display_phone_number,verified_name"},
            )
            if response.is_success:
                data = response.json()
                phone_numbers = data.get("data") if isinstance(data, dict) else None
                if isinstance(phone_numbers, list) and phone_numbers:
                    phone = phone_numbers[0]
                    if isinstance(phone, dict):
                        resolved["phone_number_id"] = resolved["phone_number_id"] or str(
                            phone.get("id") or ""
                        )
                        resolved["display_phone_number"] = resolved["display_phone_number"] or str(
                            phone.get("display_phone_number") or ""
                        )

        if resolved["phone_number_id"] and not resolved["display_phone_number"]:
            response = await client.get(
                f"{settings.whatsapp_graph_base_url.rstrip('/')}/{resolved['phone_number_id']}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "display_phone_number,verified_name"},
            )
            if response.is_success:
                data = response.json()
                if isinstance(data, dict):
                    resolved["display_phone_number"] = str(data.get("display_phone_number") or "")

    return resolved


def _business_view(business: Business, role: str) -> BusinessView:
    return BusinessView(
        id=str(business.id),
        slug=business.slug,
        name=business.name,
        primary_email=business.primary_email,
        whatsapp_number=business.whatsapp_number,
        reply_signature=business.reply_signature,
        timezone=business.timezone,
        role=role,
        ai_policy=normalized_ai_policy(business.settings),
        whatsapp_connection=normalized_whatsapp_settings(business.settings),
        website_form_key=website_form_key(business.settings),
    )


async def _inbox_stats(session: AsyncSession, business_id: UUID) -> InboxStats:
    async def count(*conditions: ColumnElement[bool]) -> int:
        value = await session.scalar(
            select(func.count(EmailThread.id)).where(
                EmailThread.business_id == business_id,
                *conditions,
            )
        )
        return int(value or 0)

    unread_value = await session.scalar(
        select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
            EmailThread.business_id == business_id
        )
    )
    whatsapp_value = await session.scalar(
        select(func.count(func.distinct(EmailThread.id)))
        .join(EmailMessage, EmailMessage.thread_id == EmailThread.id)
        .join(MailboxConnection, MailboxConnection.id == EmailMessage.mailbox_id)
        .where(
            EmailThread.business_id == business_id,
            MailboxConnection.provider == "whatsapp",
        )
    )
    return InboxStats(
        unread=int(unread_value or 0),
        needs_approval=await count(EmailThread.status == ThreadStatus.needs_approval),
        urgent=await count(EmailThread.category == ThreadCategory.urgent),
        routed_whatsapp=int(whatsapp_value or 0),
        existing_clients=await count(EmailThread.category == ThreadCategory.existing_client),
    )


async def _recent_threads(
    session: AsyncSession,
    business_id: UUID,
    *,
    search: str | None = None,
) -> list[ThreadListItem]:
    query = (
        select(EmailThread)
        .options(selectinload(EmailThread.contact))
        .where(EmailThread.business_id == business_id)
        .order_by(EmailThread.priority.desc(), EmailThread.latest_message_at.desc())
        .limit(50)
    )
    if search:
        query = query.outerjoin(Contact).where(
            EmailThread.subject.ilike(f"%{search}%") | Contact.email.ilike(f"%{search}%")
        )
    threads = (await session.scalars(query)).all()
    return [_thread_view(thread) for thread in threads]


def _thread_view(thread: EmailThread) -> ThreadListItem:
    return ThreadListItem(
        id=thread.id,
        subject=thread.subject,
        contact_name=thread.contact.name if thread.contact else None,
        contact_email=thread.contact.email if thread.contact else None,
        category=thread.category,
        status=thread.status,
        priority=thread.priority,
        is_deal=thread.is_deal,
        is_professional=thread.is_professional,
        unread_count=thread.unread_count,
        latest_message_at=thread.latest_message_at,
    )


async def _mailbox_for_provider(
    session: AsyncSession,
    business_id: UUID,
    provider: str,
) -> MailboxConnection | None:
    return await session.scalar(
        select(MailboxConnection)
        .where(
            MailboxConnection.business_id == business_id,
            MailboxConnection.provider == provider,
        )
        .order_by(MailboxConnection.updated_at.desc())
        .limit(1)
    )


async def _mailbox_status(
    session: AsyncSession,
    business_id: UUID,
    mailbox: MailboxConnection | None,
    *,
    settings: Settings,
) -> MailboxStatus:
    thread_count = int(
        await session.scalar(
            select(func.count(EmailThread.id)).where(EmailThread.business_id == business_id)
        )
        or 0
    )
    message_count = int(
        await session.scalar(
            select(func.count(EmailMessage.id))
            .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
            .where(EmailThread.business_id == business_id)
        )
        or 0
    )
    if mailbox is None:
        return MailboxStatus(
            connected=False,
            thread_count=thread_count,
            message_count=message_count,
            auto_sync_enabled=settings.mailbox_auto_sync_enabled,
            auto_sync_interval_seconds=settings.mailbox_auto_sync_interval_seconds,
        )
    return MailboxStatus(
        connected=bool(mailbox.provider_account_id and mailbox.refresh_token_encrypted),
        provider=mailbox.provider,
        email_address=mailbox.email_address,
        active=mailbox.active,
        history_start_at=mailbox.history_start_at,
        last_synced_at=mailbox.last_synced_at,
        sync_lease_until=mailbox.sync_lease_until,
        thread_count=thread_count,
        message_count=message_count,
        auto_sync_enabled=settings.mailbox_auto_sync_enabled,
        auto_sync_interval_seconds=settings.mailbox_auto_sync_interval_seconds,
    )


async def _push_status(
    session: AsyncSession,
    *,
    business_id: UUID,
    user_id: str,
    settings: Settings,
) -> PushSubscriptionStatus:
    exists = await session.scalar(
        select(PushSubscription.id).where(
            PushSubscription.business_id == business_id,
            PushSubscription.clerk_user_id == user_id,
            PushSubscription.active.is_(True),
        )
    )
    return PushSubscriptionStatus(
        enabled=exists is not None,
        vapid_public_key=settings.vapid_public_key,
    )
