import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
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
    WhatsAppConnection,
    WhatsAppConnectionMode,
    WhatsAppConnectionStatus,
    WhatsAppSignupAttempt,
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
    connection_mode: str
    coexistence_enabled: bool
    recommended: bool = False


class WhatsAppSignupAttemptPayload(BaseModel):
    connection_mode: Literal["coexistence", "cloud_api_only"] = "coexistence"
    redirect_uri: str = Field(default="", max_length=2000)


class WhatsAppSignupAttemptView(BaseModel):
    attempt_id: str
    state: str
    app_id: str
    config_id: str
    graph_version: str
    connection_mode: str
    enabled: bool
    coexistence_enabled: bool


class WhatsAppEmbeddedSignupPayload(BaseModel):
    attempt_id: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=180)
    connection_mode: Literal["coexistence", "cloud_api_only", "unknown"] = "unknown"
    code: str = Field(default="", max_length=2048)
    access_token: str = Field(default="", max_length=20000)
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
    connection_mode: str
    connection_status: str


class WhatsAppConnectionTestResult(BaseModel):
    success: bool
    calls_made: list[str]
    business_management_checked: bool = False
    whatsapp_business_management_checked: bool = False
    phone_numbers_found: int = 0
    errors: list[str] = Field(default_factory=list)

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

    preserved_status_fields = (
        "connected_via",
        "connected_at",
        "connection_mode",
        "connection_status",
        "last_error_code",
        "last_error_message",
    )
    for status_field in preserved_status_fields:
        if current_whatsapp.get(status_field) and not next_whatsapp.get(status_field):
            next_whatsapp[status_field] = current_whatsapp[status_field]
    if current_whatsapp.get("connection_mode") and next_whatsapp.get("connection_mode") in (
        "",
        "unknown",
    ):
        next_whatsapp["connection_mode"] = current_whatsapp["connection_mode"]
    if current_whatsapp.get("connection_status") and next_whatsapp.get("connection_status") in (
        "",
        "not_connected",
    ):
        next_whatsapp["connection_status"] = current_whatsapp["connection_status"]
    if current_whatsapp.get("connected_via") == "embedded_signup":
        next_whatsapp["connected_via"] = current_whatsapp["connected_via"]
        next_whatsapp["connected_at"] = current_whatsapp.get(
            "connected_at",
            payload.connected_at,
        )
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


@router.post("/{business_id}/whatsapp/test-connection", response_model=WhatsAppConnectionTestResult)
async def test_whatsapp_connection(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppConnectionTestResult:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    settings_blob = dict(business.settings or {})
    whatsapp = settings_blob.get("whatsapp")
    if not isinstance(whatsapp, dict):
        whatsapp = {}

    connection = await session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.business_id == business.id)
    )
    encrypted_token = ""
    if connection and connection.access_token_encrypted:
        encrypted_token = connection.access_token_encrypted
    elif whatsapp.get("access_token_encrypted"):
        encrypted_token = str(whatsapp["access_token_encrypted"])
    if not encrypted_token:
        raise HTTPException(status_code=409, detail="No tenant WhatsApp access token is stored")

    cipher = SecretCipher(settings.secret_encryption_key)
    try:
        access_token = cipher.decrypt(encrypted_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="Stored WhatsApp token cannot be decrypted",
        ) from exc

    calls_made: list[str] = []
    errors: list[str] = []
    business_management_checked = False
    whatsapp_business_management_checked = False
    phone_numbers_found = 0
    base_url = settings.whatsapp_graph_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        profile_response = await client.get(
            f"{base_url}/me",
            headers=headers,
            params={"fields": "id,name"},
        )
        calls_made.append("GET /me")
        if not profile_response.is_success:
            errors.append(f"public_profile check failed: {profile_response.text[:200]}")

        businesses_response = await client.get(
            f"{base_url}/me/businesses",
            headers=headers,
            params={"fields": "id,name", "limit": 25},
        )
        calls_made.append("GET /me/businesses")
        business_management_checked = businesses_response.is_success
        if not businesses_response.is_success:
            errors.append(f"business_management check failed: {businesses_response.text[:200]}")

        waba_id = ""
        if connection and connection.waba_id:
            waba_id = connection.waba_id
        elif whatsapp.get("business_account_id"):
            waba_id = str(whatsapp["business_account_id"])
        if waba_id:
            phone_response = await client.get(
                f"{base_url}/{waba_id}/phone_numbers",
                headers=headers,
                params={"fields": "id,display_phone_number,verified_name", "limit": 25},
            )
            calls_made.append("GET /{waba_id}/phone_numbers")
            whatsapp_business_management_checked = phone_response.is_success
            if phone_response.is_success:
                data = phone_response.json()
                phone_numbers = data.get("data") if isinstance(data, dict) else []
                phone_numbers_found = len(phone_numbers) if isinstance(phone_numbers, list) else 0
            else:
                errors.append(
                    f"whatsapp_business_management check failed: {phone_response.text[:200]}"
                )
        else:
            errors.append("No WABA ID stored yet; finish Embedded Signup first.")

    if connection:
        connection.last_error_code = None if not errors else "connection_test_failed"
        connection.last_error_message = None if not errors else "; ".join(errors)[:1000]
        await session.commit()

    return WhatsAppConnectionTestResult(
        success=not errors,
        calls_made=calls_made,
        business_management_checked=business_management_checked,
        whatsapp_business_management_checked=whatsapp_business_management_checked,
        phone_numbers_found=phone_numbers_found,
        errors=errors,
    )

@router.get("/{business_id}/whatsapp/embedded-config", response_model=WhatsAppEmbeddedConfig)
async def whatsapp_embedded_config(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    settings: Settings = Depends(get_settings),
    mode: Literal["coexistence", "cloud_api_only"] = "coexistence",
) -> WhatsAppEmbeddedConfig:
    del business_id
    config_id = _whatsapp_config_id_for_mode(settings, mode)
    return WhatsAppEmbeddedConfig(
        app_id=settings.meta_app_id,
        config_id=config_id,
        graph_version=settings.whatsapp_graph_base_url.rstrip("/").split("/")[-1] or "v20.0",
        enabled=bool(
            settings.meta_app_id
            and config_id
            and settings.meta_app_secret
            and (mode != "coexistence" or settings.whatsapp_coexistence_enabled)
        ),
        connection_mode=mode,
        coexistence_enabled=settings.whatsapp_coexistence_enabled,
        recommended=mode == "coexistence",
    )


@router.post("/{business_id}/whatsapp/signup-attempt", response_model=WhatsAppSignupAttemptView)
async def create_whatsapp_signup_attempt(
    business_id: UUID,
    payload: WhatsAppSignupAttemptPayload,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppSignupAttemptView:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    config_id = _whatsapp_config_id_for_mode(settings, payload.connection_mode)
    enabled = bool(
        settings.meta_app_id
        and settings.meta_app_secret
        and config_id
        and (
            payload.connection_mode != "coexistence"
            or settings.whatsapp_coexistence_enabled
        )
    )
    if not enabled:
        raise HTTPException(
            status_code=409,
            detail=(
                "Meta WhatsApp signup is not configured for this connection mode. "
                "Check META_APP_ID, META_APP_SECRET, and the matching Meta WhatsApp config ID."
            ),
        )

    attempt = WhatsAppSignupAttempt(
        business_id=business.id,
        clerk_user_id=access.user_id,
        state=secrets.token_urlsafe(48),
        connection_mode=WhatsAppConnectionMode(payload.connection_mode),
        status=WhatsAppConnectionStatus.signup_started,
        config_id=config_id,
        redirect_uri=payload.redirect_uri,
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
        meta_payload={},
    )
    session.add(attempt)
    await session.commit()

    return WhatsAppSignupAttemptView(
        attempt_id=str(attempt.id),
        state=attempt.state,
        app_id=settings.meta_app_id,
        config_id=config_id,
        graph_version=settings.whatsapp_graph_base_url.rstrip("/").split("/")[-1] or "v20.0",
        connection_mode=payload.connection_mode,
        enabled=enabled,
        coexistence_enabled=settings.whatsapp_coexistence_enabled,
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
    logger.info(
        "meta_signup_completion_received",
        business_id=str(business.id),
        user_id=access.user_id,
        code_present=bool(payload.code),
        sdk_access_token_present=bool(payload.access_token),
        waba_id_present=bool(payload.waba_id),
        phone_number_id_present=bool(payload.phone_number_id),
        display_phone_number_present=bool(payload.display_phone_number),
        attempt_id_present=bool(payload.attempt_id),
        state_present=bool(payload.state),
        connection_mode=payload.connection_mode,
    )

    attempt: WhatsAppSignupAttempt | None = None
    connection_mode = payload.connection_mode
    if payload.attempt_id or payload.state:
        attempt_conditions = [WhatsAppSignupAttempt.business_id == business.id]
        if payload.attempt_id:
            attempt_conditions.append(WhatsAppSignupAttempt.id == UUID(payload.attempt_id))
        if payload.state:
            attempt_conditions.append(WhatsAppSignupAttempt.state == payload.state)
        attempt = await session.scalar(select(WhatsAppSignupAttempt).where(*attempt_conditions))
        if attempt is None:
            raise HTTPException(status_code=403, detail="WhatsApp signup attempt is invalid")
        if attempt.clerk_user_id != access.user_id:
            raise HTTPException(
                status_code=403,
                detail="WhatsApp signup attempt belongs to another user",
            )
        if attempt.expires_at < datetime.now(UTC):
            attempt.status = WhatsAppConnectionStatus.failed
            attempt.last_error_code = "signup_attempt_expired"
            attempt.last_error_message = "The WhatsApp signup attempt expired before completion."
            await session.commit()
            raise HTTPException(
                status_code=409,
                detail="WhatsApp signup attempt expired. Please try again.",
            )
        connection_mode = attempt.connection_mode.value
        attempt.status = WhatsAppConnectionStatus.authorization_received
        attempt.meta_payload = payload.meta_payload

    if payload.code:
        try:
            logger.info(
                "meta_code_exchange_started",
                business_id=str(business.id),
                redirect_uri_present=bool(payload.redirect_uri),
            )
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
                if attempt:
                    _mark_whatsapp_attempt_failed(
                        attempt,
                        "token_exchange_failed",
                        str(token_error.detail),
                    )
                    await session.commit()
                raise code_error from token_error
    elif payload.access_token:
        logger.info("meta_embedded_signup_using_sdk_token", business_id=str(business.id))
        token_response = await _exchange_meta_access_token(settings, payload.access_token)
    else:
        raise HTTPException(status_code=422, detail="Meta did not return a code or access token")
    access_token = str(token_response.get("access_token") or "")
    logger.info(
        "meta_token_exchange_completed",
        business_id=str(business.id),
        access_token_present=bool(access_token),
        expires_in_present=bool(token_response.get("expires_in")),
    )
    if not access_token:
        logger.warning("whatsapp_embedded_signup_missing_token", business_id=str(business.id))
        if attempt:
            _mark_whatsapp_attempt_failed(
                attempt,
                "missing_token",
                "Meta did not return an access token",
            )
            await session.commit()
        raise HTTPException(status_code=400, detail="Meta did not return an access token")

    resolved = await _resolve_whatsapp_assets(
        settings=settings,
        access_token=access_token,
        waba_id=payload.waba_id,
        phone_number_id=payload.phone_number_id,
        display_phone_number=payload.display_phone_number,
        preferred_phone_number=business.whatsapp_number,
    )
    logger.info(
        "meta_whatsapp_assets_resolved",
        business_id=str(business.id),
        business_account_id_present=bool(resolved["business_account_id"]),
        phone_number_id_present=bool(resolved["phone_number_id"]),
        display_phone_number_present=bool(resolved["display_phone_number"]),
    )
    if not resolved["phone_number_id"] or not resolved["business_account_id"]:
        logger.warning(
            "whatsapp_embedded_signup_incomplete_assets",
            business_id=str(business.id),
            payload=payload.model_dump(exclude={"code", "access_token"}),
            resolved=resolved,
        )
        if attempt:
            _mark_whatsapp_attempt_failed(
                attempt,
                "missing_whatsapp_assets",
                "Meta login worked, but BeoOS could not read the WhatsApp Business Account "
                "and phone number.",
            )
            await session.commit()
        raise HTTPException(
            status_code=400,
            detail=(
                "Meta login worked, but BeoOS could not read the WhatsApp Business "
                "Account and phone number. Confirm the Meta Login for Business "
                "configuration grants business_management and whatsapp_business_management."
            ),
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
            "connection_mode": connection_mode,
            "connection_status": "connected",
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

    await _upsert_whatsapp_connection(
        session=session,
        business=business,
        access_token_encrypted=current_whatsapp["access_token_encrypted"],
        token_expires_at=token_expires_at,
        connected_by_user_id=access.user_id,
        connection_mode=connection_mode,
        resolved=resolved,
        meta_payload=payload.meta_payload,
    )
    if attempt:
        attempt.status = WhatsAppConnectionStatus.connected
        attempt.completed_at = datetime.now(UTC)
        attempt.meta_payload = payload.meta_payload

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
        connection_mode=connection_mode,
        connection_status="connected",
    )


def _whatsapp_config_id_for_mode(
    settings: Settings,
    mode: Literal["coexistence", "cloud_api_only"],
) -> str:
    if mode == "coexistence":
        return settings.meta_whatsapp_coexistence_config_id or settings.meta_whatsapp_config_id
    return settings.meta_whatsapp_cloud_config_id or settings.meta_whatsapp_config_id


def _mark_whatsapp_attempt_failed(
    attempt: WhatsAppSignupAttempt,
    code: str,
    message: str,
) -> None:
    attempt.status = WhatsAppConnectionStatus.failed
    attempt.last_error_code = code
    attempt.last_error_message = message[:1000]


async def _upsert_whatsapp_connection(
    *,
    session: AsyncSession,
    business: Business,
    access_token_encrypted: str,
    token_expires_at: str,
    connected_by_user_id: str,
    connection_mode: str,
    resolved: dict[str, str],
    meta_payload: dict[str, Any],
) -> WhatsAppConnection:
    connection = await session.scalar(
        select(WhatsAppConnection).where(WhatsAppConnection.business_id == business.id)
    )
    expires_at: datetime | None = None
    if token_expires_at:
        try:
            expires_at = datetime.fromisoformat(token_expires_at)
        except ValueError:
            expires_at = None
    if connection is None:
        connection = WhatsAppConnection(
            business_id=business.id,
            waba_id=resolved["business_account_id"],
            phone_number_id=resolved["phone_number_id"],
            access_token_encrypted=access_token_encrypted,
            connected_by_user_id=connected_by_user_id,
        )
        session.add(connection)
    connection.meta_business_id = str(meta_payload.get("business_id") or "") or None
    connection.waba_id = resolved["business_account_id"]
    connection.phone_number_id = resolved["phone_number_id"]
    connection.display_phone_number = resolved["display_phone_number"] or None
    connection.connection_mode = WhatsAppConnectionMode(connection_mode)
    connection.connection_status = WhatsAppConnectionStatus.connected
    connection.access_token_encrypted = access_token_encrypted
    connection.token_expires_at = expires_at
    connection.connected_by_user_id = connected_by_user_id
    connection.connected_at = datetime.now(UTC)
    connection.last_error_code = None
    connection.last_error_message = None
    connection.connection_metadata = {
        "connected_via": "embedded_signup",
        "meta_payload": meta_payload,
    }
    return connection


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
    preferred_phone_number: str = "",
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
                (
                    f"{settings.whatsapp_graph_base_url.rstrip('/')}/"
                    f"{resolved['business_account_id']}/phone_numbers"
                ),
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

        if not resolved["business_account_id"] or not resolved["phone_number_id"]:
            discovered = await _discover_whatsapp_assets(
                client=client,
                settings=settings,
                access_token=access_token,
                preferred_phone_number=preferred_phone_number,
            )
            for key, value in discovered.items():
                resolved[key] = resolved[key] or value

    return resolved


async def _discover_whatsapp_assets(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    access_token: str,
    preferred_phone_number: str = "",
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    base_url = settings.whatsapp_graph_base_url.rstrip("/")
    businesses = await _fetch_meta_businesses(
        client=client,
        base_url=base_url,
        headers=headers,
    )
    candidates: list[dict[str, str]] = []
    for business in businesses:
        if not isinstance(business, dict):
            continue
        nested_wabas = _nested_data(business.get("owned_whatsapp_business_accounts"))
        if nested_wabas:
            candidates.extend(_asset_candidates_from_wabas(nested_wabas))
            continue

        business_id = str(business.get("id") or "")
        if not business_id:
            continue
        wabas = await _fetch_owned_whatsapp_business_accounts(
            client=client,
            base_url=base_url,
            headers=headers,
            business_id=business_id,
        )
        for waba in wabas:
            if not isinstance(waba, dict):
                continue
            waba_id = str(waba.get("id") or "")
            phones = _nested_data(waba.get("phone_numbers"))
            if not phones and waba_id:
                phones = await _fetch_waba_phone_numbers(
                    client=client,
                    base_url=base_url,
                    headers=headers,
                    waba_id=waba_id,
                )
            candidates.extend(
                _asset_candidates_from_wabas([{**waba, "phone_numbers": {"data": phones}}])
            )

    selected = _select_whatsapp_asset_candidate(candidates, preferred_phone_number)
    if selected["business_account_id"] and selected["phone_number_id"]:
        logger.info(
            "whatsapp_embedded_signup_assets_discovered",
            business_account_id=selected["business_account_id"],
            phone_number_id=selected["phone_number_id"],
        )
        return selected
    logger.warning(
        "whatsapp_embedded_signup_asset_discovery_empty",
        businesses_checked=len(businesses),
    )
    return {"business_account_id": "", "phone_number_id": "", "display_phone_number": ""}


async def _fetch_meta_businesses(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{base_url}/me/businesses",
        headers=headers,
        params={
            "fields": (
                "id,name,"
                "owned_whatsapp_business_accounts.limit(25)"
                "{id,name,phone_numbers.limit(25){id,display_phone_number,verified_name}}"
            ),
            "limit": 25,
        },
    )
    if response.is_error:
        logger.warning(
            "meta_business_asset_lookup_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        return []
    data = response.json()
    businesses = data.get("data") if isinstance(data, dict) else None
    return businesses if isinstance(businesses, list) else []


async def _fetch_owned_whatsapp_business_accounts(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    business_id: str,
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{base_url}/{business_id}/owned_whatsapp_business_accounts",
        headers=headers,
        params={
            "fields": "id,name,phone_numbers.limit(25){id,display_phone_number,verified_name}",
            "limit": 25,
        },
    )
    if response.is_error:
        logger.warning(
            "meta_owned_waba_lookup_failed",
            status_code=response.status_code,
            business_id=business_id,
            body=response.text[:500],
        )
        return []
    data = response.json()
    wabas = data.get("data") if isinstance(data, dict) else None
    return wabas if isinstance(wabas, list) else []


async def _fetch_waba_phone_numbers(
    *,
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict[str, str],
    waba_id: str,
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{base_url}/{waba_id}/phone_numbers",
        headers=headers,
        params={"fields": "id,display_phone_number,verified_name", "limit": 25},
    )
    if response.is_error:
        logger.warning(
            "meta_waba_phone_number_lookup_failed",
            status_code=response.status_code,
            waba_id=waba_id,
            body=response.text[:500],
        )
        return []
    data = response.json()
    phones = data.get("data") if isinstance(data, dict) else None
    return phones if isinstance(phones, list) else []


def _asset_candidates_from_wabas(wabas: list[Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for waba in wabas:
        if not isinstance(waba, dict):
            continue
        waba_id = str(waba.get("id") or "")
        for phone in _nested_data(waba.get("phone_numbers")):
            if not isinstance(phone, dict):
                continue
            phone_id = str(phone.get("id") or "")
            if not waba_id or not phone_id:
                continue
            candidates.append(
                {
                    "business_account_id": waba_id,
                    "phone_number_id": phone_id,
                    "display_phone_number": str(phone.get("display_phone_number") or ""),
                }
            )
    return candidates


def _nested_data(value: Any) -> list[Any]:
    if isinstance(value, dict):
        data = value.get("data")
        return data if isinstance(data, list) else []
    if isinstance(value, list):
        return value
    return []


def _select_whatsapp_asset_candidate(
    candidates: list[dict[str, str]],
    preferred_phone_number: str,
) -> dict[str, str]:
    if not candidates:
        return {"business_account_id": "", "phone_number_id": "", "display_phone_number": ""}
    preferred = _phone_digits(preferred_phone_number)
    if preferred:
        for candidate in candidates:
            candidate_digits = _phone_digits(candidate.get("display_phone_number", ""))
            if candidate_digits and (
                candidate_digits.endswith(preferred[-10:])
                or preferred.endswith(candidate_digits[-10:])
            ):
                return candidate
    return candidates[0]


def _phone_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


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
                EmailThread.category != ThreadCategory.spam,
                EmailThread.status != ThreadStatus.closed,
                *conditions,
            )
        )
        return int(value or 0)

    unread_value = await session.scalar(
        select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
            EmailThread.business_id == business_id,
            EmailThread.category != ThreadCategory.spam,
            EmailThread.status != ThreadStatus.closed,
        )
    )
    whatsapp_value = await session.scalar(
        select(func.count(func.distinct(EmailThread.id)))
        .join(EmailMessage, EmailMessage.thread_id == EmailThread.id)
        .join(MailboxConnection, MailboxConnection.id == EmailMessage.mailbox_id)
        .where(
            EmailThread.business_id == business_id,
            EmailThread.category != ThreadCategory.spam,
            EmailThread.status != ThreadStatus.closed,
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
        .where(
            EmailThread.business_id == business_id,
            EmailThread.category != ThreadCategory.spam,
            EmailThread.status != ThreadStatus.closed,
        )
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









