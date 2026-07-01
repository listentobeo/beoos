from fastapi import APIRouter

from app.api import businesses, email, integrations, prices

api_router = APIRouter()
api_router.include_router(businesses.router)
api_router.include_router(email.router)
api_router.include_router(integrations.router)
api_router.include_router(prices.router)


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
