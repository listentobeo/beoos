import json
import re
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.email import PriceItemCreate, PriceItemView
from app.infrastructure.database import get_session
from app.infrastructure.models import PriceCatalogItem

router = APIRouter(prefix="/businesses/{business_id}/prices", tags=["prices"])


class PriceTextImport(BaseModel):
    text: str = Field(min_length=2, max_length=20_000)


class PriceImportResult(BaseModel):
    created: int
    items: list[PriceItemView]


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
            stock_quantity=item.stock_quantity,
            custom_fields=item.custom_fields,
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
    return _price_view(item)


@router.patch("/{item_id}", response_model=PriceItemView)
async def update_price(
    business_id: UUID,
    item_id: UUID,
    payload: PriceItemCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PriceItemView:
    item = await _price_item(session, business_id, item_id)
    if payload.amount_min is not None and payload.amount_max is not None:
        if payload.amount_max < payload.amount_min:
            raise HTTPException(status_code=422, detail="Maximum price cannot be below minimum")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.active = True
    item.approved_by = access.user_id
    await session.commit()
    await session.refresh(item)
    return _price_view(item)


@router.post("/import-text", response_model=PriceImportResult, status_code=201)
async def import_prices_from_text(
    business_id: UUID,
    payload: PriceTextImport,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> PriceImportResult:
    parsed_items = [_parse_price_line(line) for line in payload.text.splitlines()]
    parsed_items = [item for item in parsed_items if item is not None]
    if not parsed_items:
        raise HTTPException(
            status_code=422,
            detail=(
                "No catalogue items found. Try: service | item name | price | qty 5 | "
                "size=16x20 | medium=pencil"
            ),
        )
    items: list[PriceCatalogItem] = []
    for item_payload in parsed_items:
        item = PriceCatalogItem(
            business_id=business_id,
            **item_payload.model_dump(),
            approved_by=access.user_id,
        )
        session.add(item)
        items.append(item)
    await session.commit()
    for item in items:
        await session.refresh(item)
    return PriceImportResult(created=len(items), items=[_price_view(item) for item in items])


@router.delete("/{item_id}", status_code=204)
async def deactivate_price(
    business_id: UUID,
    item_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    item = await _price_item(session, business_id, item_id)
    item.active = False
    await session.commit()


async def _price_item(
    session: AsyncSession,
    business_id: UUID,
    item_id: UUID,
) -> PriceCatalogItem:
    item = await session.scalar(
        select(PriceCatalogItem).where(
            PriceCatalogItem.id == item_id,
            PriceCatalogItem.business_id == business_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Price item not found")
    return item


def _price_view(item: PriceCatalogItem) -> PriceItemView:
    return PriceItemView(
        id=item.id,
        service=item.service,
        label=item.label,
        amount_min=item.amount_min,
        amount_max=item.amount_max,
        currency=item.currency,
        stock_quantity=item.stock_quantity,
        custom_fields=item.custom_fields,
        source_url=item.source_url,
        effective_from=item.effective_from,
        effective_until=item.effective_until,
        active=item.active,
        approved_by=item.approved_by,
    )


def _parse_price_line(line: str) -> PriceItemCreate | None:
    text = line.strip().lstrip("-•").strip()
    if not text:
        return None
    parts = [part.strip() for part in re.split(r"\s*\|\s*|\s*,\s*", text) if part.strip()]
    if len(parts) < 2:
        return None
    service = _clean_service(parts[0])
    label = parts[1][:200]
    custom_fields: dict[str, str | int | float | bool | None] = {}
    stock_quantity: int | None = None
    amounts: list[Decimal] = []
    source_url = ""
    for part in parts[2:]:
        lower = part.lower()
        if lower.startswith(("qty ", "quantity ", "stock ")):
            number = re.search(r"\d+", part)
            if number:
                stock_quantity = int(number.group(0))
            continue
        if lower.startswith(("url=", "source=", "source_url=")):
            source_url = part.split("=", 1)[1].strip()
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            custom_fields[_clean_key(key)] = _coerce_custom_value(value.strip())
            continue
        money_match = re.search(r"(?:[^\d,.-]*\s*)?([\d,]+(?:\.\d{1,2})?)", part, re.IGNORECASE)
        if money_match:
            amounts.append(Decimal(money_match.group(1).replace(",", "")))
        else:
            custom_fields[f"note_{len(custom_fields) + 1}"] = part
    amount_min = min(amounts) if amounts else None
    amount_max = max(amounts) if len(amounts) > 1 else None
    return PriceItemCreate(
        service=service,
        label=label,
        amount_min=amount_min,
        amount_max=amount_max,
        currency="NGN",
        stock_quantity=stock_quantity,
        custom_fields=custom_fields,
        source_url=source_url,
    )


def _clean_service(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")[:80] or "general"


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")[:60] or "field"


def _coerce_custom_value(value: str) -> str | int | float | bool | None:
    try:
        loaded = json.loads(value)
        if isinstance(loaded, str | int | float | bool) or loaded is None:
            return loaded
    except json.JSONDecodeError:
        pass
    return value[:500]
