from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.business_context import (
    BusinessContextView,
    BusinessPolicyCreate,
    BusinessProfileCreate,
    BusinessServiceCreate,
    StaffAuthorityUpsert,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    BusinessPolicy,
    BusinessProfile,
    BusinessService,
    BusinessStaffAuthority,
)
from app.services.business_context import build_business_context

router = APIRouter(prefix="/businesses/{business_id}/context", tags=["business-context"])


@router.get("", response_model=BusinessContextView)
async def get_business_context(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> BusinessContextView:
    return await build_business_context(session, business_id)


@router.post("/profiles", status_code=201)
async def create_profile_version(
    business_id: UUID,
    payload: BusinessProfileCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    previous = await session.scalar(
        select(BusinessProfile)
        .where(BusinessProfile.business_id == business_id, BusinessProfile.active.is_(True))
        .order_by(BusinessProfile.version.desc())
    )
    version = await _next_version(session, BusinessProfile, business_id)
    if previous is not None:
        previous.active = False
    profile = BusinessProfile(
        business_id=business_id,
        version=version,
        supersedes_id=previous.id if previous else None,
        active=True,
        approved_by=access.user_id if payload.approval_status == "approved" else None,
        **payload.model_dump(),
    )
    session.add(profile)
    await session.flush()
    await _audit(session, business_id, access.user_id, "business_profile", profile.id, version)
    await session.commit()
    return {"id": str(profile.id), "version": version, "approval_status": profile.approval_status}


@router.post("/services", status_code=201)
async def create_service_version(
    business_id: UUID,
    payload: BusinessServiceCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    previous = await session.scalar(
        select(BusinessService)
        .where(
            BusinessService.business_id == business_id,
            BusinessService.service_key == payload.service_key,
            BusinessService.active.is_(True),
        )
        .order_by(BusinessService.version.desc())
    )
    version = await _next_version(
        session, BusinessService, business_id, BusinessService.service_key == payload.service_key
    )
    if previous is not None:
        previous.active = False
    service = BusinessService(
        business_id=business_id,
        version=version,
        supersedes_id=previous.id if previous else None,
        approved_by=access.user_id if payload.approval_status == "approved" else None,
        **payload.model_dump(),
    )
    session.add(service)
    await session.flush()
    await _audit(session, business_id, access.user_id, "business_service", service.id, version)
    await session.commit()
    return {"id": str(service.id), "version": version, "approval_status": service.approval_status}


@router.post("/policies", status_code=201)
async def create_policy_version(
    business_id: UUID,
    payload: BusinessPolicyCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    previous = await session.scalar(
        select(BusinessPolicy)
        .where(
            BusinessPolicy.business_id == business_id,
            BusinessPolicy.policy_key == payload.policy_key,
            BusinessPolicy.active.is_(True),
        )
        .order_by(BusinessPolicy.version.desc())
    )
    version = await _next_version(
        session, BusinessPolicy, business_id, BusinessPolicy.policy_key == payload.policy_key
    )
    if previous is not None:
        previous.active = False
    policy = BusinessPolicy(
        business_id=business_id,
        version=version,
        supersedes_id=previous.id if previous else None,
        approved_by=access.user_id if payload.approval_status == "approved" else None,
        **payload.model_dump(),
    )
    session.add(policy)
    await session.flush()
    await _audit(session, business_id, access.user_id, "business_policy", policy.id, version)
    await session.commit()
    return {"id": str(policy.id), "version": version, "approval_status": policy.approval_status}


@router.put("/staff/{clerk_user_id}")
async def upsert_staff_authority(
    business_id: UUID,
    clerk_user_id: str,
    payload: StaffAuthorityUpsert,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if clerk_user_id != payload.clerk_user_id:
        raise HTTPException(status_code=400, detail="Staff identity does not match route")
    authority = await session.scalar(
        select(BusinessStaffAuthority).where(
            BusinessStaffAuthority.business_id == business_id,
            BusinessStaffAuthority.clerk_user_id == clerk_user_id,
        )
    )
    values = payload.model_dump(exclude={"clerk_user_id", "approval_status"})
    if authority is None:
        authority = BusinessStaffAuthority(
            business_id=business_id,
            clerk_user_id=clerk_user_id,
            approval_status=payload.approval_status,
            **values,
        )
        session.add(authority)
    else:
        for key, value in values.items():
            setattr(authority, key, value)
        authority.approval_status = payload.approval_status
    authority.approved_by = access.user_id if payload.approval_status == "approved" else None
    await session.flush()
    await _audit(session, business_id, access.user_id, "business_staff_authority", authority.id, 1)
    await session.commit()
    return {"id": str(authority.id), "approval_status": authority.approval_status}


async def _next_version(
    session: AsyncSession,
    model: type[BusinessProfile] | type[BusinessService] | type[BusinessPolicy],
    business_id: UUID,
    *criteria: Any,
) -> int:
    value = await session.scalar(
        select(func.max(model.version)).where(model.business_id == business_id, *criteria)
    )
    return int(value or 0) + 1


async def _audit(
    session: AsyncSession,
    business_id: UUID,
    actor_id: str,
    resource_type: str,
    resource_id: UUID,
    version: int,
) -> None:
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=actor_id,
            action=f"{resource_type}.version_created",
            resource_type=resource_type,
            resource_id=str(resource_id),
            details={"version": version, "recorded_at": datetime.now(UTC).isoformat()},
        )
    )
