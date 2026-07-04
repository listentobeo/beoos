from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser, BusinessAccess, require_admin, require_user
from app.domain.business import BusinessAIPolicy, default_business_settings, normalized_ai_policy
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, BusinessMember, Role

router = APIRouter(prefix="/businesses", tags=["businesses"])


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    primary_email: EmailStr
    whatsapp_number: str = Field(min_length=8, max_length=32)
    reply_signature: str = Field(min_length=2, max_length=500)


class BusinessView(BaseModel):
    id: str
    slug: str
    name: str
    primary_email: EmailStr
    whatsapp_number: str
    reply_signature: str
    role: str
    ai_policy: BusinessAIPolicy


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
    return [
        BusinessView(
            id=str(business.id),
            slug=business.slug,
            name=business.name,
            primary_email=business.primary_email,
            whatsapp_number=business.whatsapp_number,
            reply_signature=business.reply_signature,
            role=role.value,
            ai_policy=normalized_ai_policy(business.settings),
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
        role=access.role.value,
        ai_policy=payload,
    )
