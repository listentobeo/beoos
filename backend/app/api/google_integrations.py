from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, MailboxConnection
from app.services.crypto import SecretCipher
from app.services.gmail import GmailClient

router = APIRouter(prefix="/integrations/google", tags=["integrations"])
logger = structlog.get_logger()


@router.get("/start")
async def start_google_oauth(
    business_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=400, detail="Google OAuth is not configured")
    state = jwt.encode(
        {
            "business_id": str(business_id),
            "user_id": access.user_id,
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.secret_encryption_key,
        algorithm="HS256",
    )
    return {"authorization_url": GmailClient(settings).authorization_url(state=state)}


@router.get("/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    try:
        claims = jwt.decode(state, settings.secret_encryption_key, algorithms=["HS256"])
        business_id = UUID(str(claims["business_id"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc

    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    gmail = GmailClient(settings)
    tokens = await gmail.exchange_code(code)
    access_token = str(tokens["access_token"])
    refresh_token = str(tokens.get("refresh_token") or "")
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a refresh token. Reconnect and approve offline access.",
        )
    profile = await gmail.userinfo(access_token)
    authorized_email = str(profile.get("email") or "").strip().lower()
    expected_email = business.primary_email.strip().lower()
    if authorized_email != expected_email:
        logger.warning(
            "google_oauth_account_mismatch",
            business_id=str(business.id),
            expected_email=expected_email,
            authorized_email=authorized_email,
        )
        raise HTTPException(status_code=400, detail="The authorized Google account does not match")

    mailbox = await session.scalar(
        select(MailboxConnection).where(
            MailboxConnection.business_id == business.id,
            MailboxConnection.email_address == business.primary_email,
        )
    )
    if mailbox is None:
        mailbox = MailboxConnection(
            business_id=business.id,
            provider="gmail",
            email_address=business.primary_email,
            provider_account_id=authorized_email,
            history_start_at=datetime.now(UTC) - timedelta(days=365),
        )
        session.add(mailbox)
    cipher = SecretCipher(settings.secret_encryption_key)
    mailbox.provider = "gmail"
    mailbox.provider_account_id = authorized_email
    mailbox.access_token_encrypted = cipher.encrypt(access_token)
    mailbox.refresh_token_encrypted = cipher.encrypt(refresh_token)
    mailbox.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(tokens.get("expires_in", 3600)) - 60
    )
    mailbox.active = True
    await session.commit()
    await gmail.close()
    return RedirectResponse(
        f"{str(settings.frontend_url).rstrip('/')}/dashboard/settings?gmail=connected"
    )
