from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, MailboxConnection
from app.services.crypto import SecretCipher
from app.services.zoho_mail import ZohoMailClient

router = APIRouter(prefix="/integrations/zoho", tags=["integrations"])


@router.get("/start")
async def start_zoho_oauth(
    business_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    state = jwt.encode(
        {
            "business_id": str(business_id),
            "user_id": access.user_id,
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.secret_encryption_key,
        algorithm="HS256",
    )
    return {"authorization_url": ZohoMailClient(settings).authorization_url(state=state)}


@router.get("/callback")
async def zoho_oauth_callback(
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

    zoho = ZohoMailClient(settings)
    tokens = await zoho.exchange_code(code)
    access_token = str(tokens["access_token"])
    refresh_token = str(tokens.get("refresh_token") or "")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Zoho did not return a refresh token")
    accounts = await zoho.get_accounts(access_token)
    account = next(
        (
            item
            for item in accounts
            if str(item.get("emailAddress", "")).lower() == business.primary_email.lower()
        ),
        None,
    )
    if account is None:
        raise HTTPException(status_code=400, detail="The authorized Zoho account does not match")

    mailbox = await session.scalar(
        select(MailboxConnection).where(
            MailboxConnection.business_id == business.id,
            MailboxConnection.email_address == business.primary_email,
        )
    )
    if mailbox is None:
        mailbox = MailboxConnection(
            business_id=business.id,
            email_address=business.primary_email,
            history_start_at=datetime.now(UTC) - timedelta(days=365),
        )
        session.add(mailbox)
    cipher = SecretCipher(settings.secret_encryption_key)
    mailbox.provider_account_id = str(account.get("accountId") or account.get("accountID"))
    mailbox.access_token_encrypted = cipher.encrypt(access_token)
    mailbox.refresh_token_encrypted = cipher.encrypt(refresh_token)
    mailbox.token_expires_at = datetime.now(UTC) + timedelta(
        seconds=int(tokens.get("expires_in", 3600)) - 60
    )
    mailbox.active = True
    await session.commit()
    return RedirectResponse(
        f"{str(settings.frontend_url).rstrip('/')}/dashboard/settings?zoho=connected"
    )
