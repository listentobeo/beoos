"""Add PostgreSQL-backed durable jobs.

Revision ID: 20260723_0015
Revises: 20260723_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0015"
down_revision: str | None = "20260723_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "durable_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(120), nullable=False),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id"),
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by", sa.String(160)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text()),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "business_id", "job_type", "idempotency_key", name="uq_durable_job_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','retry_scheduled','completed',"
            "'dead_letter','cancelled')",
            name="ck_durable_job_status",
        ),
    )
    op.create_index(
        "ix_durable_jobs_claim",
        "durable_jobs",
        ["status", "available_at", "priority"],
    )
    op.create_index(
        "ix_durable_jobs_business_status", "durable_jobs", ["business_id", "status"]
    )
    op.create_index("ix_durable_jobs_workflow", "durable_jobs", ["workflow_run_id"])
    op.execute(sa.text("ALTER TABLE durable_jobs ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_tenant_access ON durable_jobs FOR ALL "
            "USING (beoos_can_access_business(business_id)) "
            "WITH CHECK (beoos_can_access_business(business_id))"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_durable_job_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE related_business_id uuid;
            BEGIN
                IF NEW.workflow_run_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_runs WHERE id = NEW.workflow_run_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant durable job workflow';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_durable_jobs_tenant_integrity
            BEFORE INSERT OR UPDATE ON durable_jobs
            FOR EACH ROW EXECUTE FUNCTION beoos_assert_durable_job_tenant();
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS trg_durable_jobs_tenant_integrity ON durable_jobs")
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_durable_job_tenant()"))
    op.drop_table("durable_jobs")

