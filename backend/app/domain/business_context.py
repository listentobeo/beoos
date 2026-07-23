from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.infrastructure.models import Role

AuthorityLevel = Literal["official", "approved", "customer_provided", "inferred", "temporary"]
ApprovalStatus = Literal["draft", "approved", "rejected"]
PolicyCategory = Literal[
    "communication",
    "pricing",
    "discounts",
    "refunds",
    "commitments",
    "delivery",
    "privacy",
    "escalation",
    "prohibited_claims",
    "legal_sensitive",
    "marketing",
    "channel_specific",
]


class ProvenanceInput(BaseModel):
    source_type: str = Field(min_length=2, max_length=80)
    source_id: str = Field(min_length=1, max_length=255)
    authority_level: AuthorityLevel
    effective_from: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    approval_status: ApprovalStatus = "draft"


class BusinessProfileCreate(ProvenanceInput):
    legal_name: str = Field(default="", max_length=240)
    display_name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=10_000)
    industry: str = Field(default="", max_length=160)
    business_model: str = Field(default="", max_length=160)
    timezone: str = Field(min_length=1, max_length=64)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    opening_hours: dict[str, Any] = Field(default_factory=dict)
    contact_channels: list[dict[str, Any]] = Field(default_factory=list)
    website: str = Field(default="", max_length=2_000)
    target_markets: list[str] = Field(default_factory=list)
    customer_types: list[str] = Field(default_factory=list)


class BusinessServiceCreate(ProvenanceInput):
    service_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,119}$")
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10_000)
    active: bool = True
    base_pricing_reference: str | None = Field(default=None, max_length=255)
    required_enquiry_information: list[str] = Field(default_factory=list)
    typical_timeline: str = Field(default="", max_length=255)
    delivery_method: str = Field(default="", max_length=255)
    exclusions: list[str] = Field(default_factory=list)


class BusinessPolicyCreate(ProvenanceInput):
    policy_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,119}$")
    category: PolicyCategory
    name: str = Field(min_length=1, max_length=200)
    rules: dict[str, Any]
    active: bool = True


class StaffAuthorityUpsert(ProvenanceInput):
    clerk_user_id: str = Field(min_length=1, max_length=255)
    role: Role
    approval_authority: list[str] = Field(default_factory=list)
    financial_limit: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    channel_access: list[str] = Field(default_factory=list)
    escalation_responsibility: str = Field(default="", max_length=4_000)


class ContextReference(BaseModel):
    context_type: str
    record_id: UUID | None
    version: int | None
    classification: Literal[
        "official_fact",
        "customer_provided_statement",
        "model_inference",
        "temporary_state",
        "historical_outcome",
        "approved_correction",
    ]
    source_type: str
    source_id: str
    authority_level: str
    effective_from: datetime | None
    expires_at: datetime | None
    approval_status: str
    data: dict[str, Any]


class BusinessContextView(BaseModel):
    business_id: UUID
    built_at: datetime
    references: list[ContextReference]
    warnings: list[str]
