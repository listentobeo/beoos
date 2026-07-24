"""Add manager role and complete correction capture.

Revision ID: 20260724_0018
Revises: 20260723_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_0018"
down_revision: str | None = "20260723_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE role ADD VALUE IF NOT EXISTS 'manager' AFTER 'admin'"))
    op.add_column(
        "human_corrections",
        sa.Column(
            "changed_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "human_corrections",
        sa.Column("final_action", sa.String(80), nullable=False, server_default="reviewed"),
    )
    op.add_column(
        "human_corrections",
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("human_corrections", "result")
    op.drop_column("human_corrections", "final_action")
    op.drop_column("human_corrections", "changed_fields")
    # PostgreSQL enum values cannot be removed safely in a normal rollback. Keeping
    # manager is backward compatible with older application versions.
