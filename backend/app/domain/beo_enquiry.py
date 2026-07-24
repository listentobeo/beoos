from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CustomerIdentity(BaseModel):
    contact_id: UUID | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    previous_customer: bool = False


class BeoCommissionEnquiryInput(BaseModel):
    customer: CustomerIdentity
    channel: Literal["website_form", "gmail", "zoho", "whatsapp", "manual"]
    message: str = Field(max_length=20_000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    requested_service: str | None = None
    medium: str | None = None
    dimensions: str | None = None
    number_of_subjects: int | None = Field(default=None, ge=0)
    reference_image_available: bool | None = None
    deadline: str | None = None
    location: str | None = None
    framing: str | None = None
    delivery: str | None = None
    budget: str | None = None
    occasion: str | None = None
    urgency: bool = False
    sentiment: str | None = None
    missing_information: list[str] = Field(default_factory=list)


class BeoCommissionEnquiryOutput(BaseModel):
    structured_analysis: dict[str, Any]
    qualification_recommendation: Literal["qualified", "unqualified", "needs_information"]
    missing_questions: list[str]
    suggested_reply: str
    proposed_crm_update: dict[str, Any]
    proposed_follow_up: dict[str, Any]
    policy_result: dict[str, Any]
    approval_required: bool
    approval_reasons: list[str]
    operational_trace: list[dict[str, Any]]


class ManualCommissionEnquiryCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=200)
    customer_email: EmailStr
    customer_phone: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=20_000)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    requested_service: str | None = Field(default=None, max_length=120)
    budget: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, max_length=120)


class EnquiryOutcomeCreate(BaseModel):
    outcome_type: Literal[
        "customer_replied",
        "complete_information_received",
        "lead_qualified",
        "quote_created",
        "quote_sent",
        "quote_accepted",
        "deposit_paid",
        "order_won",
        "order_lost",
        "loss_reason",
        "response_time",
        "correction_rate",
    ]
    status: str = Field(min_length=1, max_length=40)
    value_numeric: Decimal | None = None
    value_currency: str | None = Field(default=None, min_length=3, max_length=3)
    value_text: str | None = Field(default=None, max_length=4_000)
    source: str = Field(min_length=1, max_length=80)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
