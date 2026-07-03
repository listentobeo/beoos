from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.infrastructure.models import ThreadCategory, ThreadStatus


class RecommendedAction(StrEnum):
    acknowledge = "acknowledge"
    route_whatsapp = "route_whatsapp"
    draft_email = "draft_email"
    escalate = "escalate"
    ignore = "ignore"


class ExtractedClientFields(BaseModel):
    client_name: str | None = None
    phone: str | None = None
    location: str | None = None
    budget: str | None = None
    service: str | None = None
    deadline: str | None = None
    project_details: str | None = None


class EmailTriageResult(BaseModel):
    category: ThreadCategory
    intent: str = Field(min_length=1, max_length=160)
    confidence: float = Field(ge=0, le=1)
    urgency: bool
    is_deal: bool
    is_professional: bool
    risk_flags: list[
        Literal["pricing", "payment", "refund", "complaint", "legal", "discount", "contract"]
    ]
    extracted_fields: ExtractedClientFields
    recommended_action: RecommendedAction
    acknowledgement_subject: str = Field(min_length=1, max_length=200)
    acknowledgement_body: str = Field(min_length=1, max_length=1800)


class ThreadListItem(BaseModel):
    id: UUID
    subject: str
    contact_name: str | None
    contact_email: str | None
    category: ThreadCategory
    status: ThreadStatus
    priority: int
    is_deal: bool
    is_professional: bool
    unread_count: int
    latest_message_at: datetime


class ThreadMessageView(BaseModel):
    id: UUID
    direction: str
    sender_email: EmailStr
    sender_name: str | None
    subject: str
    body_text: str
    sent_at: datetime


class DraftView(BaseModel):
    id: UUID
    subject: str
    body_text: str
    status: str
    draft_type: str
    auto_send_eligible: bool
    policy_reasons: list[str]


class DraftQueueItem(DraftView):
    thread_id: UUID
    thread_subject: str
    category: ThreadCategory
    contact_name: str | None
    contact_email: str | None
    created_at: datetime


class ThreadDetail(BaseModel):
    thread: ThreadListItem
    messages: list[ThreadMessageView]
    drafts: list[DraftView]


class InboxStats(BaseModel):
    unread: int
    needs_approval: int
    urgent: int
    routed_whatsapp: int
    existing_clients: int


class MailboxStatus(BaseModel):
    connected: bool
    email_address: EmailStr | None = None
    active: bool = False
    history_start_at: datetime | None = None
    last_synced_at: datetime | None = None
    sync_lease_until: datetime | None = None
    thread_count: int = 0
    message_count: int = 0


class MailboxSyncResult(MailboxStatus):
    imported: int


class PriceItemCreate(BaseModel):
    service: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    amount_min: Decimal | None = Field(default=None, ge=0)
    amount_max: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
    source_url: str = Field(min_length=1, max_length=2000)
    effective_from: datetime
    effective_until: datetime | None = None


class PriceItemView(PriceItemCreate):
    id: UUID
    active: bool
    approved_by: str
