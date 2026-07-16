"""Add tenant marketing intelligence metrics.

Revision ID: 20260716_0010
Revises: 20260715_0009
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0010"
down_revision: str | Sequence[str] | None = "20260715_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "marketing_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("query", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ctr", sa.Numeric(7, 4)),
        sa.Column("average_position", sa.Numeric(8, 2)),
        sa.Column("engagement_rate", sa.Numeric(7, 4)),
        sa.Column("avg_time_seconds", sa.Numeric(10, 2)),
        sa.Column("scroll_depth", sa.Numeric(7, 4)),
        sa.Column("metric_date", sa.DateTime(timezone=True)),
        sa.Column(
            "raw_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *timestamps(),
    )
    op.create_index(
        "ix_marketing_metrics_business_source",
        "marketing_metrics",
        ["business_id", "source"],
    )
    op.create_index(
        "ix_marketing_metrics_business_created",
        "marketing_metrics",
        ["business_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_marketing_metrics_business_created", table_name="marketing_metrics")
    op.drop_index("ix_marketing_metrics_business_source", table_name="marketing_metrics")
    op.drop_table("marketing_metrics")
