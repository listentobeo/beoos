"""Gate workflow deployments with tenant evaluation thresholds.

Revision ID: 20260726_0020
Revises: 20260724_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0020"
down_revision: str | None = "20260724_0019"
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
        "evaluation_thresholds",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column("metric_key", sa.String(120), nullable=False),
        sa.Column("operator", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Numeric(10, 6), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="blocking"),
        sa.Column("configured_by", sa.String(255), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id",
            "workflow_key",
            "metric_key",
            name="uq_evaluation_threshold_tenant_workflow_metric",
        ),
        sa.CheckConstraint("operator IN ('gte','lte','eq')", name="ck_evaluation_threshold_operator"),
        sa.CheckConstraint(
            "severity IN ('blocking','warning')", name="ck_evaluation_threshold_severity"
        ),
    )
    op.create_index(
        "ix_evaluation_thresholds_business_workflow",
        "evaluation_thresholds",
        ["business_id", "workflow_key"],
    )
    op.create_table(
        "workflow_deployments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_definition_id",
            UUID,
            sa.ForeignKey("workflow_definitions.id"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column("deployed_version", sa.Integer(), nullable=False),
        sa.Column("deployment_mode", sa.String(40), nullable=False),
        sa.Column(
            "evaluation_run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id"),
            nullable=False,
        ),
        sa.Column("evaluation_report", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "rollback_deployment_id",
            UUID,
            sa.ForeignKey("workflow_deployments.id"),
        ),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("deployed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "deployment_mode IN "
            "('experimental','shadow','approval_required','limited_autonomy','active')",
            name="ck_workflow_deployment_mode",
        ),
        sa.CheckConstraint(
            "status IN ('pending','deployed','rejected','rolled_back')",
            name="ck_workflow_deployment_status",
        ),
    )
    op.create_index(
        "ix_workflow_deployments_business_workflow",
        "workflow_deployments",
        ["business_id", "workflow_key"],
    )
    op.create_index(
        "ix_workflow_deployments_business_status",
        "workflow_deployments",
        ["business_id", "status"],
    )
    for table in ("evaluation_thresholds", "workflow_deployments"):
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
            CREATE OR REPLACE FUNCTION beoos_assert_deployment_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE related_business_id uuid; related_version integer;
            BEGIN
                SELECT business_id, version INTO related_business_id, related_version
                FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                IF (related_business_id IS NOT NULL
                    AND related_business_id IS DISTINCT FROM NEW.business_id)
                   OR related_version IS DISTINCT FROM NEW.deployed_version THEN
                    RAISE EXCEPTION 'invalid deployment workflow reference';
                END IF;
                SELECT business_id INTO related_business_id
                FROM evaluation_runs WHERE id = NEW.evaluation_run_id
                  AND workflow_definition_id = NEW.workflow_definition_id
                  AND status = 'completed';
                IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                    RAISE EXCEPTION 'invalid deployment evaluation reference';
                END IF;
                IF NEW.rollback_deployment_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM workflow_deployments
                    WHERE id = NEW.rollback_deployment_id
                      AND business_id = NEW.business_id
                      AND workflow_key = NEW.workflow_key
                ) THEN
                    RAISE EXCEPTION 'invalid rollback deployment reference';
                END IF;
                RETURN NEW;
            END; $$;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_workflow_deployments_tenant_integrity "
            "BEFORE INSERT OR UPDATE ON workflow_deployments "
            "FOR EACH ROW EXECUTE FUNCTION beoos_assert_deployment_tenant()"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_workflow_deployments_tenant_integrity "
            "ON workflow_deployments"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_deployment_tenant()"))
    op.drop_table("workflow_deployments")
    op.drop_table("evaluation_thresholds")
