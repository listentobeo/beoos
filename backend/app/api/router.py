import os

from fastapi import APIRouter

from app.api import (
    businesses,
    crm,
    email,
    forms,
    google_integrations,
    integrations,
    notifications,
    prices,
    quotes,
    whatsapp,
)

api_router = APIRouter()
api_router.include_router(businesses.router)
api_router.include_router(crm.router)
api_router.include_router(email.router)
api_router.include_router(forms.router)
api_router.include_router(google_integrations.router)
api_router.include_router(integrations.router)
api_router.include_router(notifications.router)
api_router.include_router(prices.router)
api_router.include_router(quotes.router)
api_router.include_router(whatsapp.router)


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    revision = os.getenv("RAILWAY_GIT_COMMIT_SHA", "local")
    return {"status": "ok", "revision": revision[:7]}
