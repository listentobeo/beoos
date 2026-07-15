from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.follow_up_scheduler import FollowUpScheduler
from app.services.mailbox_scheduler import MailboxAutoSyncScheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    scheduler: MailboxAutoSyncScheduler | None = None
    follow_up_scheduler: FollowUpScheduler | None = None
    if settings.app_env != "test":
        scheduler = MailboxAutoSyncScheduler(settings)
        scheduler.start()
        follow_up_scheduler = FollowUpScheduler(settings)
        follow_up_scheduler.start()
    try:
        yield
    finally:
        if follow_up_scheduler is not None:
            await follow_up_scheduler.stop()
        if scheduler is not None:
            await scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
<rect width="256" height="256" rx="56" fill="#171b23"/>
<rect x="18" y="18" width="220" height="220" rx="44" fill="#ed633f"/>
<text x="128" y="146" text-anchor="middle" dominant-baseline="middle"
font-family="Arial, Helvetica, sans-serif" font-size="54" font-weight="800"
fill="#ffffff" letter-spacing="-3">BeoOS</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")
