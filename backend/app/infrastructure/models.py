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
    manager = "manager"
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


class BusinessProfile(Base, TimestampMixin):
    __tablename__ = "business_profiles"
    __table_args__ = (
        UniqueConstraint("business_id", "version", name="uq_business_profile_version"),
        Index("ix_business_profiles_business_active", "business_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    industry: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    business_model: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    locations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    opening_hours: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    contact_channels: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    website: Mapped[str] = mapped_column(Text, default="", nullable=False)
    target_markets: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    customer_types: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    authority_level: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_profiles.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BusinessService(Base, TimestampMixin):
    __tablename__ = "business_services"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "service_key", "version", name="uq_business_service_version"
        ),
        Index("ix_business_services_business_active", "business_id", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    service_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_pricing_reference: Mapped[str | None] = mapped_column(String(255))
    required_enquiry_information: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    typical_timeline: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    exclusions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    authority_level: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_services.id"))


class BusinessPolicy(Base, TimestampMixin):
    __tablename__ = "business_policies"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "policy_key", "version", name="uq_business_policy_version"
        ),
        Index("ix_business_policies_business_active", "business_id", "active"),
        Index("ix_business_policies_business_category", "business_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    policy_key: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    authority_level: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_policies.id"))


class BusinessStaffAuthority(Base, TimestampMixin):
    __tablename__ = "business_staff_authorities"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "clerk_user_id", name="uq_business_staff_authority_user"
        ),
        Index("ix_business_staff_authorities_business", "business_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False)
    approval_authority: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    financial_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    channel_access: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    escalation_responsibility: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    authority_level: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))


class OnboardingSession(Base, TimestampMixin):
    __tablename__ = "onboarding_sessions"
    __table_args__ = (
        Index("ix_onboarding_sessions_business_status", "business_id", "status"),
        Index("ix_onboarding_sessions_business_activity", "business_id", "last_activity_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    onboarding_stage: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="in_progress", nullable=False)
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected_first_problem: Mapped[str | None] = mapped_column(String(120))
    current_question_key: Mapped[str | None] = mapped_column(String(160))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    draft_specification: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    activation_confirmed_by: Mapped[str | None] = mapped_column(String(255))
    activation_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deployment_mode: Mapped[str] = mapped_column(
        String(40), default="experimental", nullable=False
    )


class OnboardingResponse(Base, TimestampMixin):
    __tablename__ = "onboarding_responses"
    __table_args__ = (
        UniqueConstraint(
            "onboarding_session_id",
            "question_key",
            name="uq_onboarding_response_question",
        ),
        Index("ix_onboarding_responses_business_session", "business_id", "onboarding_session_id"),
        Index(
            "ix_onboarding_responses_confirmation",
            "business_id",
            "requires_confirmation",
            "confirmed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    onboarding_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("onboarding_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_key: Mapped[str] = mapped_column(String(160), nullable=False)
    workflow_key: Mapped[str | None] = mapped_column(String(160))
    response_type: Mapped[str] = mapped_column(String(40), nullable=False)
    response_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(255))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    skip_explanation: Mapped[str | None] = mapped_column(Text)


class WorkflowDefinition(Base, TimestampMixin):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        Index(
            "uq_workflow_definitions_tenant_key_version",
            "business_id",
            "key",
            "version",
            unique=True,
        ),
        Index("ix_workflow_definitions_business_status", "business_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"))
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    business_objective: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(80), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), default="1", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), default="1", nullable=False)
    deployment_mode: Mapped[str] = mapped_column(
        String(40), default="experimental", nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "workflow_definition_id",
            "idempotency_key",
            name="uq_workflow_run_tenant_definition_idempotency",
        ),
        Index("ix_workflow_runs_business_status", "business_id", "status"),
        Index("ix_workflow_runs_business_created", "business_id", "created_at"),
        Index("ix_workflow_runs_correlation", "business_id", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False
    )
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(80), nullable=False)
    trigger_reference_type: Mapped[str] = mapped_column(String(80), nullable=False)
    trigger_reference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_step_key: Mapped[str | None] = mapped_column(String(120))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message_sanitized: Mapped[str | None] = mapped_column(Text)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    initiated_by_user_id: Mapped[str | None] = mapped_column(String(255))


class WorkflowStep(Base, TimestampMixin):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "step_key", "sequence"),
        Index("ix_workflow_steps_business_status", "business_id", "status"),
        Index("ix_workflow_steps_run_sequence", "workflow_run_id", "sequence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    step_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message_sanitized: Mapped[str | None] = mapped_column(Text)
    step_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )


class AIExecution(Base, TimestampMixin):
    __tablename__ = "ai_executions"
    __table_args__ = (
        Index("ix_ai_executions_business_created", "business_id", "created_at"),
        Index("ix_ai_executions_run", "workflow_run_id"),
        Index("ix_ai_executions_agent_version", "agent_key", "agent_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    agent_key: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    context_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    structured_input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    structured_output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    provider_response_id: Mapped[str | None] = mapped_column(String(255))
    token_input: Mapped[int | None] = mapped_column(Integer)
    token_output: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    parse_status: Mapped[str] = mapped_column(String(40), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    safety_flags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)


class ToolDefinition(Base, TimestampMixin):
    __tablename__ = "tool_definitions"
    __table_args__ = (UniqueConstraint("key", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_reversible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_approval_by_default: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ToolPermission(Base, TimestampMixin):
    __tablename__ = "tool_permissions"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "tool_definition_id",
            "workflow_definition_id",
            "role",
            name="uq_tool_permission_scope",
        ),
        Index("ix_tool_permissions_business", "business_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tool_definitions.id"), nullable=False
    )
    workflow_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_definitions.id")
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    permission: Mapped[str] = mapped_column(String(40), nullable=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(255), nullable=False)


class ToolCall(Base, TimestampMixin):
    __tablename__ = "tool_calls"
    __table_args__ = (
        UniqueConstraint("business_id", "idempotency_key", name="uq_tool_call_idempotency"),
        Index("ix_tool_calls_business_status", "business_id", "status"),
        Index("ix_tool_calls_run", "workflow_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tool_definitions.id"), nullable=False
    )
    permission_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    request_payload_sanitized: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(96), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_payload_sanitized: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    external_reference: Mapped[str | None] = mapped_column(String(255))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message_sanitized: Mapped[str | None] = mapped_column(Text)


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_business_status", "business_id", "status"),
        Index("ix_approval_requests_run", "workflow_run_id"),
        Index("ix_approval_requests_expiry", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    proposed_action_type: Mapped[str] = mapped_column(String(120), nullable=False)
    proposed_action_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    context_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    affected_customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contacts.id"))
    financial_impact: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    requested_tool_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tool_definitions.id"))
    required_role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(255))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    final_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    execution_status: Mapped[str | None] = mapped_column(String(40))
    execution_reference: Mapped[str | None] = mapped_column(String(255))


class HumanCorrection(Base, TimestampMixin):
    __tablename__ = "human_corrections"
    __table_args__ = (
        Index("ix_human_corrections_business_created", "business_id", "created_at"),
        Index("ix_human_corrections_run", "workflow_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    ai_execution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_executions.id"))
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("approval_requests.id")
    )
    correction_type: Mapped[str] = mapped_column(String(60), nullable=False)
    original_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    corrected_value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[str] = mapped_column(String(255), nullable=False)
    final_action: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    approved_for_dataset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Outcome(Base, TimestampMixin):
    __tablename__ = "outcomes"
    __table_args__ = (
        Index("ix_outcomes_business_type", "business_id", "outcome_type"),
        Index("ix_outcomes_business_observed", "business_id", "observed_at"),
        Index("ix_outcomes_run", "workflow_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False
    )
    outcome_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    value_currency: Mapped[str | None] = mapped_column(String(3))
    value_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    outcome_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )


class Dataset(Base, TimestampMixin):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "name", "version", name="uq_dataset_tenant_name_version"
        ),
        Index("ix_datasets_business_workflow", "business_id", "workflow_key"),
        Index("ix_datasets_scope_status", "scope", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    workflow_key: Mapped[str] = mapped_column(String(160), nullable=False)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)


class DatasetExample(Base, TimestampMixin):
    __tablename__ = "dataset_examples"
    __table_args__ = (
        Index("ix_dataset_examples_dataset", "dataset_id"),
        Index("ix_dataset_examples_business_redaction", "business_id", "redaction_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expected_output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expected_policy_result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    expected_approval_requirement: Mapped[bool] = mapped_column(Boolean, nullable=False)
    labels: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(40), nullable=False)
    contains_personal_data: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    redaction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))


class EvaluationRun(Base, TimestampMixin):
    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_evaluation_runs_business_status", "business_id", "status"),
        Index("ix_evaluation_runs_workflow_version", "workflow_definition_id", "workflow_version"),
        Index("ix_evaluation_runs_dataset_version", "dataset_id", "dataset_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False
    )
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    dataset_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_examples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 6), default=0, nullable=False
    )
    average_latency: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class EvaluationResult(Base, TimestampMixin):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "dataset_example_id",
            name="uq_evaluation_result_run_example",
        ),
        Index("ix_evaluation_results_business_pass", "business_id", "pass_fail"),
        Index("ix_evaluation_results_run", "evaluation_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False
    )
    dataset_example_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_examples.id"), nullable=False
    )
    actual_output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    pass_fail: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(80))
    evaluator_type: Mapped[str] = mapped_column(String(60), nullable=False)
    evaluator_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EvaluationThreshold(Base, TimestampMixin):
    __tablename__ = "evaluation_thresholds"
    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "workflow_key",
            "metric_key",
            name="uq_evaluation_threshold_tenant_workflow_metric",
        ),
        Index("ix_evaluation_thresholds_business_workflow", "business_id", "workflow_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    workflow_key: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(120), nullable=False)
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="blocking", nullable=False)
    configured_by: Mapped[str] = mapped_column(String(255), nullable=False)


class WorkflowDeployment(Base, TimestampMixin):
    __tablename__ = "workflow_deployments"
    __table_args__ = (
        Index("ix_workflow_deployments_business_workflow", "business_id", "workflow_key"),
        Index("ix_workflow_deployments_business_status", "business_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    workflow_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False
    )
    workflow_key: Mapped[str] = mapped_column(String(160), nullable=False)
    deployed_version: Mapped[int] = mapped_column(Integer, nullable=False)
    deployment_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=False
    )
    evaluation_report: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    rollback_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_deployments.id")
    )
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DurableJob(Base, TimestampMixin):
    __tablename__ = "durable_jobs"
    __table_args__ = (
        UniqueConstraint(
            "business_id", "job_type", "idempotency_key", name="uq_durable_job_idempotency"
        ),
        Index("ix_durable_jobs_claim", "status", "available_at", "priority"),
        Index("ix_durable_jobs_business_status", "business_id", "status"),
        Index("ix_durable_jobs_workflow", "workflow_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(160))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

