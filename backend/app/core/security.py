import asyncio
import hashlib
import hmac
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.database import get_session
from app.infrastructure.models import Business, BusinessMember, ExternalAPIToken, Role


@lru_cache(maxsize=8)
def _jwk_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=3600)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    session_id: str | None


async def require_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    if not settings.clerk_jwks_url or not settings.clerk_issuer:
        raise HTTPException(status_code=503, detail="Clerk authentication is not configured")

    token = authorization.removeprefix("Bearer ").strip()

    def decode_token() -> dict[str, object]:
        signing_key = _jwk_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_aud": False, "require": ["exp", "iat", "iss", "sub"]},
        )

    try:
        claims = await asyncio.to_thread(decode_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    session_id = claims.get("sid")
    return AuthenticatedUser(
        user_id=str(claims["sub"]),
        session_id=str(session_id) if session_id is not None else None,
    )


@dataclass(frozen=True)
class BusinessAccess:
    business_id: UUID
    user_id: str
    role: Role
    correlation_id: str


async def require_business_access(
    business_id: UUID,
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> BusinessAccess:
    member = await session.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.clerk_user_id == user.user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="You do not have access to this business")
    correlation_id = (x_request_id or "").strip()[:160] or str(uuid.uuid4())
    return BusinessAccess(
        business_id=business_id,
        user_id=user.user_id,
        role=member.role,
        correlation_id=correlation_id,
    )


def require_admin(access: BusinessAccess = Depends(require_business_access)) -> BusinessAccess:
    if access.role not in {Role.owner, Role.admin}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return access


@dataclass(frozen=True)
class ExternalTokenAccess:
    business_id: UUID
    token_id: UUID
    owner_user_id: str
    scopes: tuple[str, ...]


def hash_external_api_token(raw_token: str, settings: Settings) -> str:
    return hmac.new(
        settings.secret_encryption_key.encode(),
        raw_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def _extract_external_token(
    authorization: str | None,
    x_beoos_api_key: str | None,
) -> str:
    if x_beoos_api_key:
        return x_beoos_api_key.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return ""


async def require_external_api_token(
    authorization: str | None = Header(default=None),
    x_beoos_api_key: str | None = Header(default=None, alias="X-BeoOS-API-Key"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> ExternalTokenAccess:
    raw_token = _extract_external_token(authorization, x_beoos_api_key)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing BeoOS external API token")

    token_hash = hash_external_api_token(raw_token, settings)
    token = await session.scalar(
        select(ExternalAPIToken).where(ExternalAPIToken.token_hash == token_hash)
    )
    if token is None or token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid BeoOS external API token")
    if token.expires_at is not None and token.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=401, detail="Expired BeoOS external API token")

    business_exists = await session.scalar(
        select(Business.id).where(Business.id == token.business_id)
    )
    if business_exists is None:
        raise HTTPException(status_code=401, detail="Token business no longer exists")
    membership_exists = await session.scalar(
        select(BusinessMember.id).where(
            BusinessMember.business_id == token.business_id,
            BusinessMember.clerk_user_id == token.created_by_user_id,
        )
    )
    if membership_exists is None:
        raise HTTPException(status_code=401, detail="Token owner no longer has business access")

    token.last_used_at = datetime.now(UTC)
    await session.commit()
    return ExternalTokenAccess(
        business_id=token.business_id,
        token_id=token.id,
        owner_user_id=token.created_by_user_id,
        scopes=tuple(token.scopes or []),
    )


def require_external_scope(
    required_scope: str,
) -> Callable[..., Awaitable[ExternalTokenAccess]]:
    async def dependency(
        access: ExternalTokenAccess = Depends(require_external_api_token),
    ) -> ExternalTokenAccess:
        scopes = set(access.scopes)
        if "*" not in scopes and required_scope not in scopes:
            raise HTTPException(status_code=403, detail=f"Missing scope: {required_scope}")
        return access

    return dependency
