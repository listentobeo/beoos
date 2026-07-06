from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

router = APIRouter(prefix="/businesses", tags=["businesses"])


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
    settings["whatsapp"] = payload.model_dump()
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
        whatsapp_connection=payload,
        website_form_key=website_form_key(settings),
    )
