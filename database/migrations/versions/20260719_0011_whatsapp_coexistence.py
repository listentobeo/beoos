"""Add WhatsApp coexistence connection tracking.

Revision ID: 20260719_0011
Revises: 20260716_0010
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_0011"
down_revision: str | Sequence[str] | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


whatsapp_connection_mode = postgresql.ENUM(
    "coexistence",
    "cloud_api_only",
    "unknown",
    name="whatsappconnectionmode",
    create_type=False,
)
whatsapp_connection_status = postgresql.ENUM(
    "not_connected",
    "signup_started",
    "authorization_received",
    "connecting",
    "connected",
    "action_required",
    "disconnected",
    "failed",
    name="whatsappconnectionstatus",
    create_type=False,
)
whatsapp_message_source = postgresql.ENUM(
    "customer",
    "business_app",
    "beoos_agent",
    "beoos_ai",
    "unknown",
    name="whatsappmessagesource",
    create_type=False,
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
            onupdate=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    whatsapp_connection_mode.create(op.get_bind(), checkfirst=True)
    whatsapp_connection_status.create(op.get_bind(), checkfirst=True)
    whatsapp_message_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "whatsapp_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("meta_business_id", sa.String(120)),
        sa.Column("waba_id", sa.String(120), nullable=False),
        sa.Column("phone_number_id", sa.String(120), nullable=False),
        sa.Column("display_phone_number", sa.String(40)),
        sa.Column(
            "connection_mode",
            whatsapp_connection_mode,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "connection_status",
            whatsapp_connection_status,
            nullable=False,
            server_default="not_connected",
        ),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("connected_by_user_id", sa.String(255), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_webhook_at", sa.DateTime(timezone=True)),
        sa.Column("last_history_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("last_error_message", sa.Text()),
        sa.Column(
            "connection_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
    )
    op.create_unique_constraint(
        "uq_whatsapp_connections_business_id",
        "whatsapp_connections",
        ["business_id"],
    )
    op.create_unique_constraint(
        "uq_whatsapp_connections_phone_number_id",
        "whatsapp_connections",
        ["phone_number_id"],
    )
    op.create_index(
        "ix_whatsapp_connections_waba_phone",
        "whatsapp_connections",
        ["waba_id", "phone_number_id"],
    )
    op.create_index(
        "ix_whatsapp_connections_business_status",
        "whatsapp_connections",
        ["business_id", "connection_status"],
    )

    op.create_table(
        "whatsapp_signup_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column("state", sa.String(160), unique=True, nullable=False),
        sa.Column(
            "connection_mode",
            whatsapp_connection_mode,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "status",
            whatsapp_connection_status,
            nullable=False,
            server_default="signup_started",
        ),
        sa.Column("config_id", sa.String(120), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(120)),
        sa.Column("last_error_message", sa.Text()),
        sa.Column(
            "meta_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
    )
    op.create_index(
        "ix_whatsapp_signup_business_status",
        "whatsapp_signup_attempts",
        ["business_id", "status"],
    )
    op.create_index("ix_whatsapp_signup_state", "whatsapp_signup_attempts", ["state"])

    op.create_table(
        "whatsapp_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="SET NULL"),
        ),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("waba_id", sa.String(120)),
        sa.Column("phone_number_id", sa.String(120)),
        sa.Column("message_id", sa.String(255)),
        sa.Column(
            "message_source",
            whatsapp_message_source,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "raw_event",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
    )
    op.create_unique_constraint(
        "uq_whatsapp_webhook_events_event_key",
        "whatsapp_webhook_events",
        ["event_key"],
    )
    op.create_index(
        "ix_whatsapp_events_business_created",
        "whatsapp_webhook_events",
        ["business_id", "created_at"],
    )
    op.create_index("ix_whatsapp_events_phone", "whatsapp_webhook_events", ["phone_number_id"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_events_phone", table_name="whatsapp_webhook_events")
    op.drop_index("ix_whatsapp_events_business_created", table_name="whatsapp_webhook_events")
    op.drop_constraint(
        "uq_whatsapp_webhook_events_event_key",
        "whatsapp_webhook_events",
        type_="unique",
    )
    op.drop_table("whatsapp_webhook_events")

    op.drop_index("ix_whatsapp_signup_state", table_name="whatsapp_signup_attempts")
    op.drop_index("ix_whatsapp_signup_business_status", table_name="whatsapp_signup_attempts")
    op.drop_table("whatsapp_signup_attempts")

    op.drop_index("ix_whatsapp_connections_business_status", table_name="whatsapp_connections")
    op.drop_index("ix_whatsapp_connections_waba_phone", table_name="whatsapp_connections")
    op.drop_constraint(
        "uq_whatsapp_connections_phone_number_id",
        "whatsapp_connections",
        type_="unique",
    )
    op.drop_constraint(
        "uq_whatsapp_connections_business_id",
        "whatsapp_connections",
        type_="unique",
    )
    op.drop_table("whatsapp_connections")

    whatsapp_message_source.drop(op.get_bind(), checkfirst=True)
    whatsapp_connection_status.drop(op.get_bind(), checkfirst=True)
    whatsapp_connection_mode.drop(op.get_bind(), checkfirst=True)
