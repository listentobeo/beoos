from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser, require_user
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, BusinessMember, Role

router = APIRouter(prefix="/businesses", tags=["businesses"])


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    primary_email: EmailStr
    whatsapp_number: str = Field(min_length=8, max_length=32)
    reply_signature: str = Field(min_length=2, max_length=500)


@router.get("")
async def list_businesses(
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, str]]:
    rows = (
        await session.execute(
            select(Business, BusinessMember.role)
            .join(BusinessMember, BusinessMember.business_id == Business.id)
            .where(BusinessMember.clerk_user_id == user.user_id)
            .order_by(Business.name)
        )
    ).all()
    return [
        {
            "id": str(business.id),
            "slug": business.slug,
            "name": business.name,
            "primary_email": business.primary_email,
            "whatsapp_number": business.whatsapp_number,
            "reply_signature": business.reply_signature,
            "role": role.value,
        }
        for business, role in rows
    ]


@router.post("", status_code=201)
async def create_business(
    payload: BusinessCreate,
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if await session.scalar(select(Business.id).where(Business.slug == payload.slug)):
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="Business slug already exists")
    business = Business(
        **payload.model_dump(mode="json"),
        settings={
            "auto_acknowledge": True,
            "history_days": 365,
            "price_authority": "service_pages",
            "blog_prices_are_estimates": True,
            "route_only_deals_to_whatsapp": True,
        },
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
