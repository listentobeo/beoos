"""Module 3 generic quotation engine.

Revision ID: 20260711_0004
Revises: 20260711_0003
Create Date: 2026-07-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260711_0004"
down_revision: str | Sequence[str] | None = "20260711_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

quote_status_enum = postgresql.ENUM(
    "draft",
    "needs_approval",
    "approved",
    "sent",
    "accepted",
    "rejected",
    "expired",
    name="quotestatus",
    create_type=False,
)
quote_template_enum = postgresql.ENUM(
    "mural",
    "custom",
    name="quotetemplatetype",
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
    quote_status_enum.create(bind, checkfirst=True)
    quote_template_enum.create(bind, checkfirst=True)
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_leads.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("template_type", quote_template_enum, nullable=False),
        sa.Column("status", quote_status_enum, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("deposit_required", sa.Numeric(14, 2)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("input_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calculation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("internal_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_index("ix_quotes_business_status", "quotes", ["business_id", "status"])
    op.create_index("ix_quotes_business_updated", "quotes", ["business_id", "updated_at"])


def downgrade() -> None:
    op.drop_index("ix_quotes_business_updated", table_name="quotes")
    op.drop_index("ix_quotes_business_status", table_name="quotes")
    op.drop_table("quotes")
    quote_template_enum.drop(op.get_bind(), checkfirst=True)
    quote_status_enum.drop(op.get_bind(), checkfirst=True)
