"""Add user-estimated workflow value baselines.

Revision ID: 20260726_0022
Revises: 20260726_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0022"
down_revision: str | None = "20260726_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "workflow_value_baselines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column("prior_response_time_minutes", sa.Numeric(12, 2)),
        sa.Column("manual_handling_time_minutes", sa.Numeric(12, 2)),
        sa.Column("prior_conversion_rate", sa.Numeric(7, 4)),
        sa.Column("missed_lead_frequency_monthly", sa.Numeric(12, 2)),
        sa.Column("common_mistake_cost", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("source", sa.String(40), nullable=False, server_default="user_estimate"),
        sa.Column("recorded_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "business_id",
            "workflow_key",
            name="uq_workflow_value_baseline_tenant_workflow",
        ),
        sa.CheckConstraint("source = 'user_estimate'", name="ck_workflow_baseline_source"),
        sa.CheckConstraint(
            "prior_conversion_rate IS NULL OR "
            "(prior_conversion_rate >= 0 AND prior_conversion_rate <= 1)",
            name="ck_workflow_baseline_conversion",
        ),
    )
    op.create_index(
        "ix_workflow_value_baselines_business",
        "workflow_value_baselines",
        ["business_id"],
    )
    op.execute(sa.text("ALTER TABLE workflow_value_baselines ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_tenant_access ON workflow_value_baselines FOR ALL "
            "USING (beoos_can_access_business(business_id)) "
            "WITH CHECK (beoos_can_access_business(business_id))"
        )
    )


def downgrade() -> None:
    op.drop_table("workflow_value_baselines")
