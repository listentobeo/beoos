import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.domain.business import default_business_settings
from app.infrastructure.database import SessionFactory
from app.infrastructure.models import Business, BusinessMember, PriceCatalogItem, Role

PRICE_ITEMS = [
    (
        "portrait_pencil",
        "16 x 20 inches",
        85_000,
        85_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "16 x 20 inches",
        140_000,
        140_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_pencil",
        "20 x 24 inches",
        120_000,
        120_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "20 x 24 inches",
        170_000,
        170_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_pencil",
        "24 x 30 inches",
        180_000,
        180_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "24 x 30 inches",
        250_000,
        250_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_pencil",
        "30 x 36 inches",
        280_000,
        280_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "30 x 36 inches",
        380_000,
        380_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_pencil",
        "3 x 4 feet",
        450_000,
        450_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "3 x 4 feet",
        600_000,
        600_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_pencil",
        "4 x 6 feet",
        750_000,
        750_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "portrait_painting",
        "4 x 6 feet",
        1_000_000,
        1_000_000,
        "https://www.beoarts.com/p/order-custom-portrait-in-nigeria.html",
    ),
    (
        "mural",
        "Small wall - starting price",
        200_000,
        None,
        "https://www.beoarts.com/p/mural-artist-in-nigeria.html",
    ),
    (
        "mural",
        "Medium commercial - starting price",
        500_000,
        None,
        "https://www.beoarts.com/p/mural-artist-in-nigeria.html",
    ),
    (
        "mural",
        "Large or institutional - starting price",
        1_000_000,
        None,
        "https://www.beoarts.com/p/mural-artist-in-nigeria.html",
    ),
    (
        "live_painting",
        "Individual package",
        170_000,
        250_000,
        "https://www.beoarts.com/p/live-event-painting-services-in-nigeria.html",
    ),
    (
        "live_painting",
        "Grand package",
        300_000,
        450_000,
        "https://www.beoarts.com/p/live-event-painting-services-in-nigeria.html",
    ),
    (
        "live_painting",
        "Executive package - starting price",
        500_000,
        None,
        "https://www.beoarts.com/p/live-event-painting-services-in-nigeria.html",
    ),
]


async def seed() -> None:
    settings = get_settings()
    if not settings.bootstrap_clerk_user_id:
        raise RuntimeError("BOOTSTRAP_CLERK_USER_ID is required for the initial owner")
    async with SessionFactory() as session:
        business = await session.scalar(select(Business).where(Business.slug == "beo-art-studio"))
        if business is None:
            business = Business(
                slug="beo-art-studio",
                name="Beo Art Studio",
                primary_email="admin@beoarts.com",
                whatsapp_number="+2349075424681",
                reply_signature="Benjamin Odeke\nBeo Art Studio",
                settings=default_business_settings(),
            )
            session.add(business)
            await session.flush()
        member = await session.scalar(
            select(BusinessMember).where(
                BusinessMember.business_id == business.id,
                BusinessMember.clerk_user_id == settings.bootstrap_clerk_user_id,
            )
        )
        if member is None:
            session.add(
                BusinessMember(
                    business_id=business.id,
                    clerk_user_id=settings.bootstrap_clerk_user_id,
                    role=Role.owner,
                )
            )
        has_prices = await session.scalar(
            select(PriceCatalogItem.id).where(PriceCatalogItem.business_id == business.id).limit(1)
        )
        if has_prices is None:
            for service, label, amount_min, amount_max, source_url in PRICE_ITEMS:
                session.add(
                    PriceCatalogItem(
                        business_id=business.id,
                        service=service,
                        label=label,
                        amount_min=Decimal(amount_min),
                        amount_max=Decimal(amount_max) if amount_max is not None else None,
                        source_url=source_url,
                        effective_from=datetime.now(UTC),
                        approved_by=settings.bootstrap_clerk_user_id,
                    )
                )
        await session.commit()
        print(f"Seeded {business.name} ({business.id})")


if __name__ == "__main__":
    asyncio.run(seed())

