"""AI lead qualification fields.

Revision ID: 20260712_0006
Revises: 20260712_0005
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260712_0006"
down_revision: str | Sequence[str] | None = "20260712_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

temperature_enum = postgresql.ENUM("hot", "warm", "cold", name="leadtemperature")


def upgrade() -> None:
    temperature_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("crm_leads", sa.Column("lead_score", sa.Integer(), server_default="20", nullable=False))
    op.add_column(
        "crm_leads",
        sa.Column("temperature", temperature_enum, server_default="cold", nullable=False),
    )
    op.add_column(
        "crm_leads",
        sa.Column("qualification_summary", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "crm_leads",
        sa.Column(
            "qualification_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column("crm_leads", sa.Column("last_qualified_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("crm_leads", "last_qualified_at")
    op.drop_column("crm_leads", "qualification_reasons")
    op.drop_column("crm_leads", "qualification_summary")
    op.drop_column("crm_leads", "temperature")
    op.drop_column("crm_leads", "lead_score")
    temperature_enum.drop(op.get_bind(), checkfirst=True)
