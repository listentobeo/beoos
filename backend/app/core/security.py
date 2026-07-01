import asyncio
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.database import get_session
from app.infrastructure.models import BusinessMember, Role


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


async def require_business_access(
    business_id: UUID,
    user: AuthenticatedUser = Depends(require_user),
    session: AsyncSession = Depends(get_session),
) -> BusinessAccess:
    member = await session.scalar(
        select(BusinessMember).where(
            BusinessMember.business_id == business_id,
            BusinessMember.clerk_user_id == user.user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="You do not have access to this business")
    return BusinessAccess(business_id=business_id, user_id=user.user_id, role=member.role)


def require_admin(access: BusinessAccess = Depends(require_business_access)) -> BusinessAccess:
    if access.role not in {Role.owner, Role.admin}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return access
