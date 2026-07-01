from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.email import PriceItemCreate, PriceItemView
from app.infrastructure.database import get_session
from app.infrastructure.models import PriceCatalogItem

router = APIRouter(prefix="/businesses/{business_id}/prices", tags=["prices"])


@router.get("", response_model=list[PriceItemView])
async def list_prices(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[PriceItemView]:
    items = (
        await session.scalars(
            select(PriceCatalogItem)
            .where(PriceCatalogItem.business_id == business_id)
            .order_by(PriceCatalogItem.service, PriceCatalogItem.amount_min)
        )
    ).all()
    return [
        PriceItemView(
            id=item.id,
            service=item.service,
            label=item.label,
            amount_min=item.amount_min,
            amount_max=item.amount_max,
            currency=item.currency,
            source_url=item.source_url,
            effective_from=item.effective_from,
            effective_until=item.effective_until,
            active=item.active,
            approved_by=item.approved_by,
        )
        for item in items
    ]


@router.post("", response_model=PriceItemView, status_code=201)
async def create_price(
    business_id: UUID,
    payload: PriceItemCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PriceItemView:
    if payload.amount_min is not None and payload.amount_max is not None:
        if payload.amount_max < payload.amount_min:
            raise HTTPException(status_code=422, detail="Maximum price cannot be below minimum")
    item = PriceCatalogItem(
        business_id=business_id,
        **payload.model_dump(),
        approved_by=access.user_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return PriceItemView(
        id=item.id,
        service=item.service,
        label=item.label,
        amount_min=item.amount_min,
        amount_max=item.amount_max,
        currency=item.currency,
        source_url=item.source_url,
        effective_from=item.effective_from,
        effective_until=item.effective_until,
        active=item.active,
        approved_by=item.approved_by,
    )


@router.delete("/{item_id}", status_code=204)
async def deactivate_price(
    business_id: UUID,
    item_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    item = await session.scalar(
        select(PriceCatalogItem).where(
            PriceCatalogItem.id == item_id,
            PriceCatalogItem.business_id == business_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Price item not found")
    item.active = False
    await session.commit()
