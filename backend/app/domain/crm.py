from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.infrastructure.models import LeadSource, LeadStage


class CRMLeadCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    contact_id: UUID | None = None
    thread_id: UUID | None = None
    stage: LeadStage = LeadStage.new
    source: LeadSource = LeadSource.manual
    service: str | None = Field(default=None, max_length=120)
    budget: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, max_length=160)
    estimated_value: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    probability: int = Field(default=20, ge=0, le=100)
    next_follow_up_at: datetime | None = None
    notes: str = Field(default="", max_length=5000)


class CRMLeadUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    stage: LeadStage
    service: str | None = Field(default=None, max_length=120)
    budget: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, max_length=160)
    estimated_value: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    probability: int = Field(default=20, ge=0, le=100)
    next_follow_up_at: datetime | None = None
    notes: str = Field(default="", max_length=5000)


class CRMLeadFromThread(BaseModel):
    stage: LeadStage = LeadStage.new
    notes: str = Field(default="", max_length=5000)


class CRMLeadView(BaseModel):
    id: UUID
    business_id: UUID
    contact_id: UUID | None
    thread_id: UUID | None
    title: str
    stage: LeadStage
    source: LeadSource
    service: str | None
    budget: str | None
    deadline: str | None
    estimated_value: Decimal | None
    currency: str
    probability: int
    next_follow_up_at: datetime | None
    notes: str
    owner_id: str | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    thread_subject: str | None = None


class CRMPipelineStats(BaseModel):
    total: int
    open: int
    won: int
    lost: int
    estimated_open_value: Decimal
    needs_follow_up: int
