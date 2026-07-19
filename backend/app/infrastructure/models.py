import enum
import secrets
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Role(enum.StrEnum):
    owner = "owner"
    admin = "admin"
    agent = "agent"
    viewer = "viewer"


class ThreadCategory(enum.StrEnum):
    portrait = "portrait"
    mural = "mural"
    live_painting = "live_painting"
    sfx = "sfx"
    art_school = "art_school"
    existing_client = "existing_client"
    corporate = "corporate"
    general = "general"
    urgent = "urgent"
    spam = "spam"


class ThreadStatus(enum.StrEnum):
    new = "new"
    acknowledged = "acknowledged"
    needs_approval = "needs_approval"
    routed_whatsapp = "routed_whatsapp"
    waiting_client = "waiting_client"
    closed = "closed"


class Direction(enum.StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class DraftStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    failed = "failed"


class LeadStage(enum.StrEnum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    quote_needed = "quote_needed"
    quoted = "quoted"
    deposit_pending = "deposit_pending"
    won = "won"
    lost = "lost"


class LeadSource(enum.StrEnum):
    email = "email"
    gmail = "gmail"
    zoho = "zoho"
    whatsapp = "whatsapp"
    website_form = "website_form"
    manual = "manual"


class LeadTemperature(enum.StrEnum):
    hot = "hot"
    warm = "warm"
    cold = "cold"


class QuoteStatus(enum.StrEnum):
    draft = "draft"
    needs_approval = "needs_approval"
    approved = "approved"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


class QuoteTemplateType(enum.StrEnum):
    mural = "mural"
    custom = "custom"


class FollowUpStatus(enum.StrEnum):
    scheduled = "scheduled"
    draft_created = "draft_created"
    skipped = "skipped"
    cancelled = "cancelled"
    failed = "failed"


class WhatsAppConnectionMode(enum.StrEnum):
    coexistence = "coexistence"
    cloud_api_only = "cloud_api_only"
    unknown = "unknown"


class WhatsAppConnectionStatus(enum.StrEnum):
    not_connected = "not_connected"
    signup_started = "signup_started"
    authorization_received = "authorization_received"
    connecting = "connecting"
    connected = "connected"
    action_required = "action_required"
    disconnected = "disconnected"
    failed = "failed"


class WhatsAppMessageSource(enum.StrEnum):
    customer = "customer"
    business_app = "business_app"
    beoos_agent = "beoos_agent"
    beoos_ai = "beoos_ai"
    unknown = "unknown"


class MarketingMetric(Base, TimestampMixin):
    __tablename__ = "marketing_metrics"
    __table_args__ = (
        Index("ix_marketing_metrics_business_source", "business_id", "source"),
        Index("ix_marketing_metrics_business_created", "business_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    page_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    query: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    average_position: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    engagement_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    avg_time_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    scroll_depth: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    metric_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class Business(Base, TimestampMixin):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    primary_email: Mapped[str] = mapped_column(String(320), nullable=False)
    whatsapp_number: Mapped[str] = mapped_column(String(32), nullable=False)
    reply_signature: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Lagos", nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class BusinessMember(Base, TimestampMixin):
    __tablename__ = "business_members"
    __table_args__ = (UniqueConstraint("business_id", "clerk_user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.owner, nullable=False)


class ExternalAPIToken(Base, TimestampMixin):
    __tablename__ = "external_api_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        Index("ix_external_api_tokens_business_active", "business_id", "revoked_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(96), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class WhatsAppConnection(Base, TimestampMixin):
    __tablename__ = "whatsapp_connections"
    __table_args__ = (
        UniqueConstraint("business_id"),
        UniqueConstraint("phone_number_id"),
        Index("ix_whatsapp_connections_waba_phone", "waba_id", "phone_number_id"),
        Index("ix_whatsapp_connections_business_status", "business_id", "connection_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    meta_business_id: Mapped[str | None] = mapped_column(String(120))
    waba_id: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(String(120), nullable=False)
    display_phone_number: Mapped[str | None] = mapped_column(String(40))
    connection_mode: Mapped[WhatsAppConnectionMode] = mapped_column(
        Enum(WhatsAppConnectionMode), default=WhatsAppConnectionMode.unknown, nullable=False
    )
    connection_status: Mapped[WhatsAppConnectionStatus] = mapped_column(
        Enum(WhatsAppConnectionStatus),
        default=WhatsAppConnectionStatus.not_connected,
        nullable=False,
    )
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_history_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    connection_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class WhatsAppSignupAttempt(Base, TimestampMixin):
    __tablename__ = "whatsapp_signup_attempts"
    __table_args__ = (
        Index("ix_whatsapp_signup_business_status", "business_id", "status"),
        Index("ix_whatsapp_signup_state", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    connection_mode: Mapped[WhatsAppConnectionMode] = mapped_column(
        Enum(WhatsAppConnectionMode), default=WhatsAppConnectionMode.unknown, nullable=False
    )
    status: Mapped[WhatsAppConnectionStatus] = mapped_column(
        Enum(WhatsAppConnectionStatus),
        default=WhatsAppConnectionStatus.signup_started,
        nullable=False,
    )
    config_id: Mapped[str] = mapped_column(String(120), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(120))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    meta_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class WhatsAppWebhookEvent(Base, TimestampMixin):
    __tablename__ = "whatsapp_webhook_events"
    __table_args__ = (
        UniqueConstraint("event_key"),
        Index("ix_whatsapp_events_business_created", "business_id", "created_at"),
        Index("ix_whatsapp_events_phone", "phone_number_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    waba_id: Mapped[str | None] = mapped_column(String(120))
    phone_number_id: Mapped[str | None] = mapped_column(String(120))
    message_id: Mapped[str | None] = mapped_column(String(255))
    message_source: Mapped[WhatsAppMessageSource] = mapped_column(
        Enum(WhatsAppMessageSource), default=WhatsAppMessageSource.unknown, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_event: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class MailboxConnection(Base, TimestampMixin):
    __tablename__ = "mailbox_connections"
    __table_args__ = (UniqueConstraint("business_id", "email_address"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="zoho", nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    provider_account_id: Mapped[str | None] = mapped_column(String(128))
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("business_id", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_existing_client: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_channel: Mapped[str] = mapped_column(String(20), default="email", nullable=False)


class EmailThread(Base, TimestampMixin):
    __tablename__ = "email_threads"
    __table_args__ = (
        UniqueConstraint("business_id", "provider_thread_id"),
        Index("ix_threads_business_latest", "business_id", "latest_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    provider_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, default="(no subject)", nullable=False)
    category: Mapped[ThreadCategory] = mapped_column(
        Enum(ThreadCategory), default=ThreadCategory.general, nullable=False
    )
    status: Mapped[ThreadStatus] = mapped_column(
        Enum(ThreadStatus), default=ThreadStatus.new, nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_deal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_professional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latest_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    contact: Mapped[Contact | None] = relationship()
    messages: Mapped[list["EmailMessage"]] = relationship(
        back_populates="thread", order_by="EmailMessage.sent_at", cascade="all, delete-orphan"
    )


class EmailMessage(Base, TimestampMixin):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("mailbox_id", "provider_message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_threads.id"), nullable=False)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mailbox_connections.id"), nullable=False
    )
    provider_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    direction: Mapped[Direction] = mapped_column(Enum(Direction), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(200))
    recipients: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    subject: Mapped[str] = mapped_column(Text, default="(no subject)", nullable=False)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text)
    attachment_metadata: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thread: Mapped[EmailThread] = relationship(back_populates="messages")


class EmailAnalysis(Base, TimestampMixin):
    __tablename__ = "email_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_messages.id"), unique=True, nullable=False
    )
    category: Mapped[ThreadCategory] = mapped_column(Enum(ThreadCategory), nullable=False)
    intent: Mapped[str] = mapped_column(String(160), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    urgency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_professional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    response_id: Mapped[str | None] = mapped_column(String(255))


class EmailDraft(Base, TimestampMixin):
    __tablename__ = "email_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("email_threads.id"), nullable=False)
    source_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("email_messages.id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus), default=DraftStatus.pending, nullable=False
    )
    draft_type: Mapped[str] = mapped_column(String(40), nullable=False)
    auto_send_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))


class PriceCatalogItem(Base, TimestampMixin):
    __tablename__ = "price_catalog_items"
    __table_args__ = (Index("ix_price_business_active", "business_id", "active"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    service: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    stock_quantity: Mapped[int | None] = mapped_column(Integer)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)


class PushSubscription(Base, TimestampMixin):
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("business_id", "clerk_user_id", "endpoint"),
        Index("ix_push_subscriptions_business_active", "business_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CRMLead(Base, TimestampMixin):
    __tablename__ = "crm_leads"
    __table_args__ = (
        UniqueConstraint("business_id", "thread_id"),
        Index("ix_crm_leads_business_stage", "business_id", "stage"),
        Index("ix_crm_leads_business_updated", "business_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    thread_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_threads.id"))
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    stage: Mapped[LeadStage] = mapped_column(Enum(LeadStage), default=LeadStage.new, nullable=False)
    source: Mapped[LeadSource] = mapped_column(
        Enum(LeadSource), default=LeadSource.manual, nullable=False
    )
    service: Mapped[str | None] = mapped_column(String(120))
    budget: Mapped[str | None] = mapped_column(String(120))
    deadline: Mapped[str | None] = mapped_column(String(160))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    lead_score: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    temperature: Mapped[LeadTemperature] = mapped_column(
        Enum(LeadTemperature), default=LeadTemperature.cold, nullable=False
    )
    qualification_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    qualification_reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    last_qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(255))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact: Mapped[Contact | None] = relationship()
    thread: Mapped[EmailThread | None] = relationship()


class FollowUpTask(Base, TimestampMixin):
    __tablename__ = "follow_up_tasks"
    __table_args__ = (
        Index("ix_follow_up_business_status_due", "business_id", "status", "scheduled_for"),
        Index("ix_follow_up_lead_status", "lead_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("crm_leads.id"), nullable=False)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("email_threads.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    sequence_name: Mapped[str] = mapped_column(String(80), default="standard", nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    status: Mapped[FollowUpStatus] = mapped_column(
        Enum(FollowUpStatus), default=FollowUpStatus.scheduled, nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subject: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    task_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    lead: Mapped[CRMLead] = relationship()
    thread: Mapped[EmailThread | None] = relationship()
    contact: Mapped[Contact | None] = relationship()


class QuoteTemplate(Base, TimestampMixin):
    __tablename__ = "quote_templates"
    __table_args__ = (
        UniqueConstraint("business_id", "name"),
        Index("ix_quote_templates_business_active", "business_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    template_type: Mapped[QuoteTemplateType] = mapped_column(
        Enum(QuoteTemplateType), default=QuoteTemplateType.custom, nullable=False
    )
    field_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    default_input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    design_settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    terms_settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Quote(Base, TimestampMixin):
    __tablename__ = "quotes"
    __table_args__ = (
        Index("ix_quotes_business_status", "business_id", "status"),
        Index("ix_quotes_business_updated", "business_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("quote_templates.id"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crm_leads.id"))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    public_token: Mapped[str] = mapped_column(
        String(96), unique=True, default=lambda: secrets.token_urlsafe(32), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    template_type: Mapped[QuoteTemplateType] = mapped_column(
        Enum(QuoteTemplateType), default=QuoteTemplateType.custom, nullable=False
    )
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus), default=QuoteStatus.draft, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    deposit_required: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    calculation: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    proposal: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    internal_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_url: Mapped[str | None] = mapped_column(Text)
    payment_reference: Mapped[str | None] = mapped_column(String(160))

    lead: Mapped[CRMLead | None] = relationship()
    contact: Mapped[Contact | None] = relationship()
    template: Mapped[QuoteTemplate | None] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_business_created", "business_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

