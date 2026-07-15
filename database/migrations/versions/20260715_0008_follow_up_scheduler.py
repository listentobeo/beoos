"""Add follow-up scheduler tasks.

Revision ID: 20260715_0008
Revises: 20260713_0007
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0008"
down_revision: str | Sequence[str] | None = "20260713_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    follow_up_status = postgresql.ENUM(
        "scheduled",
        "draft_created",
        "skipped",
        "cancelled",
        "failed",
        name="followupstatus",
    )
    follow_up_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "follow_up_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True)),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sequence_name", sa.String(length=80), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("status", follow_up_status, nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column(
            "task_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["crm_leads.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["email_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_follow_up_business_status_due",
        "follow_up_tasks",
        ["business_id", "status", "scheduled_for"],
    )
    op.create_index("ix_follow_up_lead_status", "follow_up_tasks", ["lead_id", "status"])
    op.alter_column("follow_up_tasks", "task_metadata", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_follow_up_lead_status", table_name="follow_up_tasks")
    op.drop_index("ix_follow_up_business_status_due", table_name="follow_up_tasks")
    op.drop_table("follow_up_tasks")
    postgresql.ENUM(name="followupstatus").drop(op.get_bind(), checkfirst=True)
