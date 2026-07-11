"""Module 2 CRM lead pipeline.

Revision ID: 20260711_0003
Revises: 20260706_0002
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_0003"
down_revision: str | Sequence[str] | None = "20260706_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

lead_stage_enum = postgresql.ENUM(
    "new",
    "contacted",
    "qualified",
    "quote_needed",
    "quoted",
    "deposit_pending",
    "won",
    "lost",
    name="leadstage",
    create_type=False,
)
lead_source_enum = postgresql.ENUM(
    "email",
    "gmail",
    "zoho",
    "whatsapp",
    "website_form",
    "manual",
    name="leadsource",
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
    bind = op.get_bind()
    lead_stage_enum.create(bind, checkfirst=True)
    lead_source_enum.create(bind, checkfirst=True)
    op.create_table(
        "crm_leads",
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
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("stage", lead_stage_enum, nullable=False),
        sa.Column("source", lead_source_enum, nullable=False),
        sa.Column("service", sa.String(120)),
        sa.Column("budget", sa.String(120)),
        sa.Column("deadline", sa.String(160)),
        sa.Column("estimated_value", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(255)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("business_id", "thread_id"),
    )
    op.create_index("ix_crm_leads_business_stage", "crm_leads", ["business_id", "stage"])
    op.create_index("ix_crm_leads_business_updated", "crm_leads", ["business_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_crm_leads_business_updated", table_name="crm_leads")
    op.drop_index("ix_crm_leads_business_stage", table_name="crm_leads")
    op.drop_table("crm_leads")
    lead_source_enum.drop(op.get_bind(), checkfirst=True)
    lead_stage_enum.drop(op.get_bind(), checkfirst=True)
