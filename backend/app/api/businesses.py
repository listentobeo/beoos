from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, BusinessMember, Role
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
    code: str = Field(min_length=8, max_length=2048)
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

    token_response = await _exchange_meta_code(
        settings,
        payload.code,
        redirect_uri=payload.redirect_uri,
    )
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
    params = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "code": code,
    }
    if redirect_uri:
        params["redirect_uri"] = redirect_uri
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.get(
            f"{settings.whatsapp_graph_base_url.rstrip('/')}/oauth/access_token",
            params=params,
        )
    if response.is_error:
        logger.warning(
            "meta_code_exchange_failed",
            status_code=response.status_code,
            body=response.text[:500],
        )
        raise HTTPException(status_code=400, detail="Could not exchange Meta authorization code")
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
