"""Complete WhatsApp Business app coexistence onboarding and synchronization.

Revision ID: 20260727_0027
Revises: 20260726_0026
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260727_0027"
down_revision: str | Sequence[str] | None = "20260726_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_connections",
        sa.Column("embedded_signup_version", sa.String(20), nullable=False, server_default="v4"),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("webhook_subscribed_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("coexistence_verified_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("sync_deadline_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column(
            "contacts_sync_status",
            sa.String(40),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("contacts_sync_request_id", sa.String(160)),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column(
            "history_sync_status",
            sa.String(40),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("history_sync_request_id", sa.String(160)),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("history_sync_phase", sa.Integer()),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("history_sync_progress", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "whatsapp_connections",
        sa.Column("sync_completed_at", sa.DateTime(timezone=True)),
    )
    op.create_check_constraint(
        "ck_whatsapp_contacts_sync_status",
        "whatsapp_connections",
        "contacts_sync_status IN "
        "('not_requested','queued','requested','receiving','completed','declined','failed')",
    )
    op.create_check_constraint(
        "ck_whatsapp_history_sync_status",
        "whatsapp_connections",
        "history_sync_status IN "
        "('not_requested','queued','requested','receiving','completed','declined','failed')",
    )
    op.create_check_constraint(
        "ck_whatsapp_history_sync_progress",
        "whatsapp_connections",
        "history_sync_progress >= 0 AND history_sync_progress <= 100",
    )

    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("payload_hash", sa.String(96), nullable=False, server_default=""),
    )
    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
    )
    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("phase", sa.Integer()),
    )
    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("chunk_order", sa.Integer()),
    )
    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("progress", sa.Integer()),
    )
    op.add_column(
        "whatsapp_webhook_events",
        sa.Column("processing_error", sa.Text()),
    )
    op.create_check_constraint(
        "ck_whatsapp_webhook_event_status",
        "whatsapp_webhook_events",
        "status IN ('queued','processing','processed','ignored','failed')",
    )
    op.create_check_constraint(
        "ck_whatsapp_webhook_progress",
        "whatsapp_webhook_events",
        "progress IS NULL OR (progress >= 0 AND progress <= 100)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_whatsapp_webhook_progress",
        "whatsapp_webhook_events",
        type_="check",
    )
    op.drop_constraint(
        "ck_whatsapp_webhook_event_status",
        "whatsapp_webhook_events",
        type_="check",
    )
    for column_name in (
        "processing_error",
        "progress",
        "chunk_order",
        "phase",
        "status",
        "payload_hash",
    ):
        op.drop_column("whatsapp_webhook_events", column_name)

    op.drop_constraint(
        "ck_whatsapp_history_sync_progress",
        "whatsapp_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_whatsapp_history_sync_status",
        "whatsapp_connections",
        type_="check",
    )
    op.drop_constraint(
        "ck_whatsapp_contacts_sync_status",
        "whatsapp_connections",
        type_="check",
    )
    for column_name in (
        "sync_completed_at",
        "history_sync_progress",
        "history_sync_phase",
        "history_sync_request_id",
        "history_sync_status",
        "contacts_sync_request_id",
        "contacts_sync_status",
        "sync_deadline_at",
        "coexistence_verified_at",
        "webhook_subscribed_at",
        "embedded_signup_version",
    ):
        op.drop_column("whatsapp_connections", column_name)
