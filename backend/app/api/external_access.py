import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, hash_external_api_token, require_admin
from app.infrastructure.database import get_session
from app.infrastructure.models import AuditLog, Business, ExternalAPIRequestLog, ExternalAPIToken

router = APIRouter(prefix="/businesses/{business_id}/external-access", tags=["external-access"])

DEFAULT_READ_SCOPES = [
    "business:read",
    "inbox:read",
    "crm:read",
    "pricing:read",
    "quotes:read",
    "analytics:read",
    "marketing:read",
]
ALLOWED_EXTERNAL_SCOPES = frozenset(
    [
        *DEFAULT_READ_SCOPES,
        "marketing:propose",
    ]
)


class ExternalTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: DEFAULT_READ_SCOPES.copy(), max_length=30)
    expires_in_days: int | None = Field(default=365, ge=1, le=730)


class ExternalTokenCreated(BaseModel):
    id: UUID
    name: str
    token: str
    token_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime


class ExternalTokenView(BaseModel):
    id: UUID
    name: str
    token_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class ExternalRequestView(BaseModel):
    id: UUID
    token_id: UUID
    correlation_id: str
    method: str
    tool_name: str
    status: str
    latency_ms: int
    error_code: str | None
    error_message_safe: str | None
    created_at: datetime


@router.get("/tokens", response_model=list[ExternalTokenView])
async def list_external_tokens(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ExternalTokenView]:
    tokens = (
        await session.scalars(
            select(ExternalAPIToken)
            .where(ExternalAPIToken.business_id == business_id)
            .order_by(ExternalAPIToken.created_at.desc())
        )
    ).all()
    return [_token_view(token) for token in tokens]


@router.get("/requests", response_model=list[ExternalRequestView])
async def list_external_requests(
    business_id: UUID,
    limit: int = 50,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[ExternalRequestView]:
    safe_limit = max(1, min(limit, 200))
    rows = (
        await session.scalars(
            select(ExternalAPIRequestLog)
            .where(ExternalAPIRequestLog.business_id == business_id)
            .order_by(ExternalAPIRequestLog.created_at.desc())
            .limit(safe_limit)
        )
    ).all()
    return [
        ExternalRequestView(
            id=row.id,
            token_id=row.token_id,
            correlation_id=row.correlation_id,
            method=row.method,
            tool_name=row.tool_name,
            status=row.status,
            latency_ms=row.latency_ms,
            error_code=row.error_code,
            error_message_safe=row.error_message_safe,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/tokens", response_model=ExternalTokenCreated, status_code=201)
async def create_external_token(
    business_id: UUID,
    payload: ExternalTokenCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ExternalTokenCreated:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")

    scopes = _validated_scopes(payload.scopes)
    raw_token = _new_external_token()
    now = datetime.now(UTC)
    expires_at = None
    if payload.expires_in_days:
        expires_at = now + timedelta(days=payload.expires_in_days)
    token = ExternalAPIToken(
        business_id=business_id,
        name=payload.name.strip(),
        token_prefix=raw_token[:18],
        token_hash=hash_external_api_token(raw_token, settings),
        scopes=scopes,
        created_by_user_id=access.user_id,
        expires_at=expires_at,
    )
    session.add(token)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="external_api_token.created",
            resource_type="external_api_token",
            resource_id=str(token.id),
            details={"name": token.name, "scopes": token.scopes},
        )
    )
    await session.commit()
    await session.refresh(token)
    return ExternalTokenCreated(
        id=token.id,
        name=token.name,
        token=raw_token,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        expires_at=token.expires_at,
        created_at=token.created_at,
    )


@router.post("/tokens/{token_id}/rotate", response_model=ExternalTokenCreated)
async def rotate_external_token(
    business_id: UUID,
    token_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ExternalTokenCreated:
    token = await session.scalar(
        select(ExternalAPIToken).where(
            ExternalAPIToken.id == token_id,
            ExternalAPIToken.business_id == business_id,
        )
    )
    if token is None:
        raise HTTPException(status_code=404, detail="External token not found")
    if token.revoked_at is not None:
        raise HTTPException(status_code=409, detail="Revoked tokens cannot be rotated")
    raw_token = _new_external_token()
    token.token_prefix = raw_token[:18]
    token.token_hash = hash_external_api_token(raw_token, settings)
    token.last_used_at = None
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="external_api_token.rotated",
            resource_type="external_api_token",
            resource_id=str(token.id),
            details={"name": token.name, "scopes": token.scopes},
        )
    )
    await session.commit()
    await session.refresh(token)
    return ExternalTokenCreated(
        id=token.id,
        name=token.name,
        token=raw_token,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        expires_at=token.expires_at,
        created_at=token.created_at,
    )


@router.delete("/tokens/{token_id}", status_code=204)
async def revoke_external_token(
    business_id: UUID,
    token_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    token = await session.scalar(
        select(ExternalAPIToken).where(
            ExternalAPIToken.id == token_id,
            ExternalAPIToken.business_id == business_id,
        )
    )
    if token is None:
        raise HTTPException(status_code=404, detail="External token not found")
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        session.add(
            AuditLog(
                business_id=business_id,
                actor_id=access.user_id,
                action="external_api_token.revoked",
                resource_type="external_api_token",
                resource_id=str(token.id),
                details={"name": token.name},
            )
        )
        await session.commit()


def _token_view(token: ExternalAPIToken) -> ExternalTokenView:
    return ExternalTokenView(
        id=token.id,
        name=token.name,
        token_prefix=token.token_prefix,
        scopes=token.scopes,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
        created_at=token.created_at,
    )


def _new_external_token() -> str:
    return f"beoos_{secrets.token_urlsafe(36)}"


def _validated_scopes(scopes: list[str]) -> list[str]:
    selected = sorted(set(scopes or DEFAULT_READ_SCOPES))
    unknown = set(selected) - ALLOWED_EXTERNAL_SCOPES
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported external token scope(s): {', '.join(sorted(unknown))}",
        )
    return selected
