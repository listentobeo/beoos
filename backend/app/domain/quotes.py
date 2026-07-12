from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infrastructure.models import QuoteStatus, QuoteTemplateType


class MuralDimensions(BaseModel):
    width: Decimal = Field(default=Decimal("16"), ge=0)
    height: Decimal = Field(default=Decimal("7"), ge=0)
    unit: str = Field(default="ft", pattern="^(ft|m)$")


class MuralQuoteInput(BaseModel):
    client_name: str = Field(default="Client Name", max_length=200)
    organization: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=320)
    address: str = Field(default="", max_length=500)
    project_title: str = Field(default="Mural Project", min_length=2, max_length=240)
    project_type: str = Field(default="school", max_length=80)
    project_location: str = Field(default="", max_length=500)
    deadline: str = Field(default="", max_length=160)
    dimensions: MuralDimensions = Field(default_factory=MuralDimensions)
    surface_type: str = Field(default="Smooth", max_length=120)
    surface_condition: str = Field(default="Good", max_length=120)
    access: str = Field(default="Ground Level", max_length=120)
    environment: str = Field(default="Indoor", max_length=120)
    problem: str = Field(default="", max_length=3000)
    objectives: str = Field(default="", max_length=3000)
    solution: str = Field(default="", max_length=3000)
    success_criteria: str = Field(default="", max_length=3000)
    design_costs: dict[str, Decimal] = Field(default_factory=dict)
    labor: list[dict[str, Decimal | str]] = Field(default_factory=list)
    materials: dict[str, Decimal] = Field(default_factory=dict)
    equipment: dict[str, Decimal] = Field(default_factory=dict)
    transport: dict[str, Decimal] = Field(default_factory=dict)
    project_management_percent: Decimal = Field(default=Decimal("10"), ge=0)
    overhead_percent: Decimal = Field(default=Decimal("10"), ge=0)
    risk_percent: Decimal = Field(default=Decimal("7.5"), ge=0)
    profit_percent: Decimal = Field(default=Decimal("30"), ge=0)
    payment_terms: str = Field(
        default="70% mobilization, 30% before final handover.",
        max_length=1000,
    )
    timeline: str = Field(
        default="Design and production timeline to be agreed after approval.",
        max_length=1000,
    )
    assumptions: str = Field(default="", max_length=3000)
    exclusions: str = Field(default="", max_length=3000)
    warranty: str = Field(default="", max_length=3000)


class QuoteCreate(BaseModel):
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    title: str = Field(min_length=2, max_length=240)
    template_type: QuoteTemplateType = QuoteTemplateType.mural
    input_data: dict[str, Any] = Field(default_factory=dict)
    valid_until: datetime | None = None


class QuoteUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    status: QuoteStatus = QuoteStatus.draft
    input_data: dict[str, Any] = Field(default_factory=dict)
    valid_until: datetime | None = None
    internal_notes: str = Field(default="", max_length=5000)


class QuoteView(BaseModel):
    id: UUID
    business_id: UUID
    lead_id: UUID | None
    contact_id: UUID | None
    title: str
    template_type: QuoteTemplateType
    status: QuoteStatus
    currency: str
    subtotal: Decimal
    total: Decimal
    deposit_required: Decimal | None
    public_url: str | None = None
    valid_until: datetime | None
    input_data: dict[str, Any]
    calculation: dict[str, Any]
    proposal: dict[str, Any]
    internal_notes: str
    approved_by: str | None
    sent_at: datetime | None
    client_viewed_at: datetime | None = None
    accepted_at: datetime | None
    payment_url: str | None = None
    payment_reference: str | None = None
    created_at: datetime
    updated_at: datetime
    lead_title: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None


class PublicQuoteView(BaseModel):
    title: str
    business_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    status: QuoteStatus
    currency: str
    total: Decimal
    deposit_required: Decimal | None
    proposal: dict[str, Any]
    calculation: dict[str, Any]
    payment_url: str | None = None
    accepted_at: datetime | None = None


class PublicQuoteAcceptResult(BaseModel):
    success: bool = True
    status: QuoteStatus
    accepted_at: datetime
    payment_url: str | None = None
