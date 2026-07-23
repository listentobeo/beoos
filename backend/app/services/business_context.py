from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.business_context import BusinessContextView, ContextReference
from app.infrastructure.models import (
    Business,
    BusinessPolicy,
    BusinessProfile,
    BusinessService,
    PriceCatalogItem,
)


async def build_business_context(
    session: AsyncSession, business_id: UUID
) -> BusinessContextView:
    now = datetime.now(UTC)
    business = await session.get(Business, business_id)
    if business is None:
        raise ValueError("Business not found")
    references: list[ContextReference] = []
    warnings: list[str] = []

    profile = await session.scalar(
        select(BusinessProfile)
        .where(
            BusinessProfile.business_id == business_id,
            BusinessProfile.active.is_(True),
            BusinessProfile.approval_status == "approved",
            BusinessProfile.effective_from <= now,
            or_(BusinessProfile.expires_at.is_(None), BusinessProfile.expires_at > now),
        )
        .order_by(BusinessProfile.version.desc())
    )
    if profile is not None:
        references.append(
            _reference(
                "business_profile",
                profile,
                {
                    "legal_name": profile.legal_name,
                    "display_name": profile.display_name,
                    "description": profile.description,
                    "industry": profile.industry,
                    "business_model": profile.business_model,
                    "timezone": profile.timezone,
                    "locations": profile.locations,
                    "opening_hours": profile.opening_hours,
                    "contact_channels": profile.contact_channels,
                    "website": profile.website,
                    "target_markets": profile.target_markets,
                    "customer_types": profile.customer_types,
                },
            )
        )
    else:
        warnings.append("No approved typed business profile; using legacy business fields")
        references.append(
            ContextReference(
                context_type="business_profile",
                record_id=business.id,
                version=None,
                classification="temporary_state",
                source_type="legacy_business_record",
                source_id=str(business.id),
                authority_level="temporary",
                effective_from=business.updated_at,
                expires_at=None,
                approval_status="unversioned",
                data={
                    "display_name": business.name,
                    "timezone": business.timezone,
                    "primary_email": business.primary_email,
                    "whatsapp_number": business.whatsapp_number,
                },
            )
        )

    services = (
        await session.scalars(
            select(BusinessService)
            .where(
                BusinessService.business_id == business_id,
                BusinessService.active.is_(True),
                BusinessService.approval_status == "approved",
                BusinessService.effective_from <= now,
                or_(BusinessService.expires_at.is_(None), BusinessService.expires_at > now),
            )
            .order_by(BusinessService.service_key, BusinessService.version.desc())
        )
    ).all()
    seen_services: set[str] = set()
    for service in services:
        if service.service_key in seen_services:
            continue
        seen_services.add(service.service_key)
        references.append(
            _reference(
                "business_service",
                service,
                {
                    "service_key": service.service_key,
                    "name": service.name,
                    "category": service.category,
                    "description": service.description,
                    "base_pricing_reference": service.base_pricing_reference,
                    "required_enquiry_information": service.required_enquiry_information,
                    "typical_timeline": service.typical_timeline,
                    "delivery_method": service.delivery_method,
                    "exclusions": service.exclusions,
                },
            )
        )

    policies = (
        await session.scalars(
            select(BusinessPolicy)
            .where(
                BusinessPolicy.business_id == business_id,
                BusinessPolicy.active.is_(True),
                BusinessPolicy.approval_status == "approved",
                BusinessPolicy.effective_from <= now,
                or_(BusinessPolicy.expires_at.is_(None), BusinessPolicy.expires_at > now),
            )
            .order_by(BusinessPolicy.policy_key, BusinessPolicy.version.desc())
        )
    ).all()
    seen_policies: set[str] = set()
    for policy in policies:
        if policy.policy_key in seen_policies:
            continue
        seen_policies.add(policy.policy_key)
        references.append(
            _reference(
                "business_policy",
                policy,
                {
                    "policy_key": policy.policy_key,
                    "category": policy.category,
                    "name": policy.name,
                    "rules": policy.rules,
                },
            )
        )
    if not seen_policies and isinstance(business.settings.get("ai_policy"), dict):
        warnings.append("No approved typed policies; legacy AI policy is temporary context")
        references.append(
            ContextReference(
                context_type="business_policy",
                record_id=business.id,
                version=None,
                classification="temporary_state",
                source_type="legacy_business_settings",
                source_id=f"{business.id}:ai_policy",
                authority_level="temporary",
                effective_from=business.updated_at,
                expires_at=None,
                approval_status="unversioned",
                data={"category": "communication", "rules": business.settings["ai_policy"]},
            )
        )

    prices = (
        await session.scalars(
            select(PriceCatalogItem).where(
                PriceCatalogItem.business_id == business_id,
                PriceCatalogItem.active.is_(True),
            )
        )
    ).all()
    for price in prices:
        references.append(
            ContextReference(
                context_type="official_price",
                record_id=price.id,
                version=None,
                classification="official_fact",
                source_type="price_catalog",
                source_id=str(price.id),
                authority_level="official",
                effective_from=price.effective_from,
                expires_at=price.effective_until,
                approval_status="approved",
                data={
                    "service": price.service,
                    "label": price.label,
                    "amount_min": str(price.amount_min) if price.amount_min is not None else None,
                    "amount_max": str(price.amount_max) if price.amount_max is not None else None,
                    "currency": price.currency,
                },
            )
        )
    return BusinessContextView(
        business_id=business_id,
        built_at=now,
        references=references,
        warnings=warnings,
    )


def _reference(
    context_type: str,
    record: BusinessProfile | BusinessService | BusinessPolicy,
    data: dict[str, Any],
) -> ContextReference:
    classification = (
        "official_fact"
        if record.authority_level in {"official", "approved"}
        else "customer_provided_statement"
        if record.authority_level == "customer_provided"
        else "model_inference"
        if record.authority_level == "inferred"
        else "temporary_state"
    )
    return ContextReference(
        context_type=context_type,
        record_id=record.id,
        version=record.version,
        classification=classification,
        source_type=record.source_type,
        source_id=record.source_id,
        authority_level=record.authority_level,
        effective_from=record.effective_from,
        expires_at=record.expires_at,
        approval_status=record.approval_status,
        data=data,
    )
