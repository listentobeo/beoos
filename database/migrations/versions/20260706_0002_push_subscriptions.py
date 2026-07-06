"""Module 1.7 push notification subscriptions.

Revision ID: 20260706_0002
Revises: 20260701_0001
Create Date: 2026-07-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260706_0002"
down_revision: str | Sequence[str] | None = "20260701_0001"
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
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clerk_user_id", sa.String(255), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("business_id", "clerk_user_id", "endpoint"),
    )
    op.create_index(
        "ix_push_subscriptions_business_active",
        "push_subscriptions",
        ["business_id", "active"],
    )
    op.create_index(
        "ix_push_subscriptions_clerk_user_id",
        "push_subscriptions",
        ["clerk_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_clerk_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_business_active", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
