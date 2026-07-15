"""Add tenant quote templates and flexible quote template links.

Revision ID: 20260715_0009
Revises: 20260715_0008
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0009"
down_revision: str | Sequence[str] | None = "20260715_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    op.create_table(
        "quote_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_type", quote_template_enum, nullable=False, server_default="custom"),
        sa.Column(
            "field_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "default_input",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "design_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "terms_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *timestamps(),
        sa.UniqueConstraint("business_id", "name"),
    )
    op.create_index(
        "ix_quote_templates_business_active",
        "quote_templates",
        ["business_id", "active"],
    )
    op.add_column(
        "quotes",
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quote_templates.id", ondelete="SET NULL"),
        ),
    )


def downgrade() -> None:
    op.drop_column("quotes", "template_id")
    op.drop_index("ix_quote_templates_business_active", table_name="quote_templates")
    op.drop_table("quote_templates")
