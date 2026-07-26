"""Add approval-controlled marketing opportunities and experiments.

Revision ID: 20260726_0023
Revises: 20260726_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0023"
down_revision: str | None = "20260726_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def upgrade() -> None:
    op.create_table(
        "marketing_opportunities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("page_or_query", sa.Text(), nullable=False),
        sa.Column("baseline_metrics", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(7, 4)),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending_approval"),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN "
            "('pending_approval','approved','in_progress','completed','dismissed')",
            name="ck_marketing_opportunity_status",
        ),
    )
    op.create_index(
        "ix_marketing_opportunities_business_status",
        "marketing_opportunities",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_marketing_opportunities_business_source",
        "marketing_opportunities",
        ["business_id", "source"],
    )
    op.create_table(
        "marketing_experiments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            UUID,
            sa.ForeignKey("marketing_opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("approved_change", sa.Text(), nullable=False),
        sa.Column("target_page", sa.Text(), nullable=False),
        sa.Column("baseline_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comparison_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comparison_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("implementation_date", sa.DateTime(timezone=True)),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("execution_method", sa.String(40), nullable=False),
        sa.Column("approved_tool_call_id", UUID, sa.ForeignKey("tool_calls.id")),
        sa.Column("status", sa.String(40), nullable=False, server_default="approved"),
        sa.Column("result", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("lesson", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
        sa.CheckConstraint(
            "execution_method IN ('manual','approved_tool')",
            name="ck_marketing_experiment_execution",
        ),
        sa.CheckConstraint(
            "status IN ('approved','measurement_pending','completed','cancelled')",
            name="ck_marketing_experiment_status",
        ),
        sa.CheckConstraint(
            "baseline_period_start < baseline_period_end "
            "AND baseline_period_end <= comparison_period_start "
            "AND comparison_period_start < comparison_period_end",
            name="ck_marketing_experiment_periods",
        ),
    )
    op.create_index(
        "ix_marketing_experiments_business_status",
        "marketing_experiments",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_marketing_experiments_opportunity",
        "marketing_experiments",
        ["opportunity_id"],
    )
    for table in ("marketing_opportunities", "marketing_experiments"):
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY beoos_tenant_access ON {table} FOR ALL "
                "USING (beoos_can_access_business(business_id)) "
                "WITH CHECK (beoos_can_access_business(business_id))"
            )
        )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_marketing_experiment_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM marketing_opportunities
                    WHERE id = NEW.opportunity_id AND business_id = NEW.business_id
                ) THEN RAISE EXCEPTION 'cross-tenant marketing opportunity';
                END IF;
                IF NEW.approved_tool_call_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM tool_calls
                    WHERE id = NEW.approved_tool_call_id
                      AND business_id = NEW.business_id
                      AND status = 'completed'
                ) THEN RAISE EXCEPTION 'invalid approved marketing tool call';
                END IF;
                RETURN NEW;
            END; $$;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_marketing_experiments_tenant_integrity "
            "BEFORE INSERT OR UPDATE ON marketing_experiments "
            "FOR EACH ROW EXECUTE FUNCTION beoos_assert_marketing_experiment_tenant()"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_marketing_experiments_tenant_integrity "
            "ON marketing_experiments"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_marketing_experiment_tenant()"))
    op.drop_table("marketing_experiments")
    op.drop_table("marketing_opportunities")
