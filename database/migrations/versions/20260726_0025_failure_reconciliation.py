"""Standardize external action failure recovery and reconciliation.

Revision ID: 20260726_0025
Revises: 20260726_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0025"
down_revision: str | None = "20260726_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("tool_calls", sa.Column("failure_category", sa.String(60)))
    op.add_column(
        "tool_calls",
        sa.Column("external_state", sa.String(40), nullable=False, server_default="not_started"),
    )
    op.add_column(
        "tool_calls",
        sa.Column(
            "reconciliation_status",
            sa.String(40),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.create_check_constraint(
        "ck_tool_call_external_state",
        "tool_calls",
        "external_state IN "
        "('not_started','not_applicable','in_flight','confirmed','not_completed','unknown')",
    )
    op.create_check_constraint(
        "ck_tool_call_reconciliation",
        "tool_calls",
        "reconciliation_status IN "
        "('not_required','required','pending','reconciled','failed','cancelled')",
    )
    op.create_table(
        "external_action_reconciliations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        ),
        sa.Column("tool_call_id", UUID, sa.ForeignKey("tool_calls.id", ondelete="SET NULL")),
        sa.Column("durable_job_id", UUID, sa.ForeignKey("durable_jobs.id", ondelete="SET NULL")),
        sa.Column("action_type", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(96), nullable=False),
        sa.Column("failure_category", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("provider_reference", sa.String(255)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("resolution", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_by", sa.String(255)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "business_id",
            "action_type",
            "idempotency_key",
            name="uq_external_reconciliation_idempotency",
        ),
        sa.CheckConstraint(
            "failure_category IN "
            "('authentication','authorization','validation','rate_limit','timeout',"
            "'provider_unavailable','malformed_output','missing_context','duplicate_event',"
            "'external_action_unknown','payment_pending','permanent_failure','human_timeout')",
            name="ck_external_reconciliation_failure_category",
        ),
        sa.CheckConstraint(
            "status IN "
            "('pending','investigating','retry_scheduled','reconciled','failed','cancelled')",
            name="ck_external_reconciliation_status",
        ),
    )
    op.create_index(
        "ix_external_reconciliations_business_status",
        "external_action_reconciliations",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_external_reconciliations_tool_call",
        "external_action_reconciliations",
        ["tool_call_id"],
    )
    op.execute(
        sa.text("ALTER TABLE external_action_reconciliations ENABLE ROW LEVEL SECURITY")
    )
    op.execute(
        sa.text(
            "CREATE POLICY beoos_tenant_access ON external_action_reconciliations FOR ALL "
            "USING (beoos_can_access_business(business_id)) "
            "WITH CHECK (beoos_can_access_business(business_id))"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_reconciliation_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.tool_call_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM tool_calls
                    WHERE id = NEW.tool_call_id AND business_id = NEW.business_id
                ) THEN RAISE EXCEPTION 'cross-tenant reconciliation tool call';
                END IF;
                IF NEW.durable_job_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM durable_jobs
                    WHERE id = NEW.durable_job_id AND business_id = NEW.business_id
                ) THEN RAISE EXCEPTION 'cross-tenant reconciliation job';
                END IF;
                RETURN NEW;
            END; $$;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_external_reconciliations_tenant_integrity "
            "BEFORE INSERT OR UPDATE ON external_action_reconciliations "
            "FOR EACH ROW EXECUTE FUNCTION beoos_assert_reconciliation_tenant()"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_external_reconciliations_tenant_integrity "
            "ON external_action_reconciliations"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_reconciliation_tenant()"))
    op.drop_table("external_action_reconciliations")
    op.drop_constraint("ck_tool_call_reconciliation", "tool_calls", type_="check")
    op.drop_constraint("ck_tool_call_external_state", "tool_calls", type_="check")
    op.drop_column("tool_calls", "reconciliation_status")
    op.drop_column("tool_calls", "external_state")
    op.drop_column("tool_calls", "failure_category")
