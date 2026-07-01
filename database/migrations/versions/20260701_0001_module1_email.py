"""Module 1 multi-business email foundation.

Revision ID: 20260701_0001
Revises:
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260701_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role_enum = postgresql.ENUM("owner", "admin", "agent", "viewer", name="role", create_type=False)
category_enum = postgresql.ENUM(
    "portrait",
    "mural",
    "live_painting",
    "sfx",
    "art_school",
    "existing_client",
    "corporate",
    "general",
    "urgent",
    "spam",
    name="threadcategory",
    create_type=False,
)
status_enum = postgresql.ENUM(
    "new",
    "acknowledged",
    "needs_approval",
    "routed_whatsapp",
    "waiting_client",
    "closed",
    name="threadstatus",
    create_type=False,
)
direction_enum = postgresql.ENUM("inbound", "outbound", name="direction", create_type=False)
draft_status_enum = postgresql.ENUM(
    "pending", "approved", "rejected", "sent", "failed", name="draftstatus", create_type=False
)


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (role_enum, category_enum, status_enum, direction_enum, draft_status_enum):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("primary_email", sa.String(320), nullable=False),
        sa.Column("whatsapp_number", sa.String(32), nullable=False),
        sa.Column("reply_signature", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "business_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("business_id", "clerk_user_id"),
    )
    op.create_index("ix_business_members_clerk_user_id", "business_members", ["clerk_user_id"])
    op.create_table(
        "mailbox_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("provider_account_id", sa.String(128)),
        sa.Column("access_token_encrypted", sa.Text()),
        sa.Column("refresh_token_encrypted", sa.Text()),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("history_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("sync_lease_until", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("business_id", "email_address"),
    )
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("phone", sa.String(40)),
        sa.Column("is_existing_client", sa.Boolean(), nullable=False),
        sa.Column("preferred_channel", sa.String(20), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("business_id", "email"),
    )
    op.create_table(
        "email_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("provider_thread_id", sa.String(255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_deal", sa.Boolean(), nullable=False),
        sa.Column("is_professional", sa.Boolean(), nullable=False),
        sa.Column("latest_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("business_id", "provider_thread_id"),
    )
    op.create_index(
        "ix_threads_business_latest",
        "email_threads",
        ["business_id", sa.text("latest_message_at DESC")],
    )
    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mailbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mailbox_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column("sender_name", sa.String(200)),
        sa.Column("recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text()),
        sa.Column("attachment_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("mailbox_id", "provider_message_id"),
    )
    op.create_table(
        "email_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("intent", sa.String(160), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("urgency", sa.Boolean(), nullable=False),
        sa.Column("is_deal", sa.Boolean(), nullable=False),
        sa.Column("is_professional", sa.Boolean(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_action", sa.String(80), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("response_id", sa.String(255)),
        *timestamps(),
    )
    op.create_table(
        "email_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", draft_status_enum, nullable=False),
        sa.Column("draft_type", sa.String(40), nullable=False),
        sa.Column("auto_send_eligible", sa.Boolean(), nullable=False),
        sa.Column("policy_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(255)),
        *timestamps(),
    )
    op.create_table(
        "price_catalog_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("amount_min", sa.Numeric(14, 2)),
        sa.Column("amount_max", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        *timestamps(),
    )
    op.create_index(
        "ix_price_business_active", "price_catalog_items", ["business_id", "active"]
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_business_created", "audit_logs", ["business_id", "created_at"])

    # Supabase exposes the public schema through PostgREST. These tables are backend-only;
    # enabling RLS with no client policy prevents accidental anon/authenticated access.
    for table_name in (
        "businesses",
        "business_members",
        "mailbox_connections",
        "contacts",
        "email_threads",
        "email_messages",
        "email_analyses",
        "email_drafts",
        "price_catalog_items",
        "audit_logs",
    ):
        op.execute(sa.text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.drop_index("ix_audit_business_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_price_business_active", table_name="price_catalog_items")
    op.drop_table("price_catalog_items")
    op.drop_table("email_drafts")
    op.drop_table("email_analyses")
    op.drop_table("email_messages")
    op.drop_index("ix_threads_business_latest", table_name="email_threads")
    op.drop_table("email_threads")
    op.drop_table("contacts")
    op.drop_table("mailbox_connections")
    op.drop_index("ix_business_members_clerk_user_id", table_name="business_members")
    op.drop_table("business_members")
    op.drop_table("businesses")
    bind = op.get_bind()
    for enum_type in reversed(
        (role_enum, category_enum, status_enum, direction_enum, draft_status_enum)
    ):
        enum_type.drop(bind, checkfirst=True)
