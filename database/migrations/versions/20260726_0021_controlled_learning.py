"""Add privacy-reviewed dataset candidates and improvement suggestions.

Revision ID: 20260726_0021
Revises: 20260726_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0021"
down_revision: str | None = "20260726_0020"
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
        "dataset_candidates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column(
            "human_correction_id",
            UUID,
            sa.ForeignKey("human_corrections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_dataset_id", UUID, sa.ForeignKey("datasets.id")),
        sa.Column("input_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expected_output", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correction_reason", sa.Text(), nullable=False),
        sa.Column("contains_personal_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("contains_sensitive_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("redaction_status", sa.String(40), nullable=False),
        sa.Column("privacy_reviewed_by", sa.String(255)),
        sa.Column("privacy_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending_privacy"),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("dataset_example_id", UUID, sa.ForeignKey("dataset_examples.id")),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id", "human_correction_id", name="uq_dataset_candidate_correction"
        ),
        sa.CheckConstraint(
            "redaction_status IN ('not_required','pending','redacted','rejected')",
            name="ck_dataset_candidate_redaction",
        ),
        sa.CheckConstraint(
            "status IN ('pending_privacy','ready_for_approval','approved','rejected')",
            name="ck_dataset_candidate_status",
        ),
        sa.CheckConstraint(
            "NOT (contains_personal_data OR contains_sensitive_data) "
            "OR redaction_status <> 'not_required'",
            name="ck_dataset_candidate_private_redaction",
        ),
    )
    op.create_index(
        "ix_dataset_candidates_business_status",
        "dataset_candidates",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_dataset_candidates_workflow",
        "dataset_candidates",
        ["business_id", "workflow_key"],
    )
    op.create_table(
        "improvement_suggestions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column("suggestion_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="proposed"),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('proposed','accepted_for_review','dismissed')",
            name="ck_improvement_suggestion_status",
        ),
        sa.CheckConstraint("occurrence_count > 0", name="ck_improvement_occurrence_count"),
    )
    op.create_index(
        "ix_improvement_suggestions_business_status",
        "improvement_suggestions",
        ["business_id", "status"],
    )
    op.create_index(
        "ix_improvement_suggestions_workflow",
        "improvement_suggestions",
        ["business_id", "workflow_key"],
    )
    for table in ("dataset_candidates", "improvement_suggestions"):
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
            CREATE OR REPLACE FUNCTION beoos_assert_learning_tenant()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM human_corrections
                    WHERE id = NEW.human_correction_id
                      AND business_id = NEW.business_id
                      AND workflow_run_id = NEW.workflow_run_id
                ) THEN RAISE EXCEPTION 'invalid dataset candidate correction';
                END IF;
                IF NEW.target_dataset_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM datasets
                    WHERE id = NEW.target_dataset_id
                      AND business_id = NEW.business_id
                      AND workflow_key = NEW.workflow_key
                ) THEN RAISE EXCEPTION 'invalid dataset candidate target';
                END IF;
                IF NEW.dataset_example_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM dataset_examples
                    WHERE id = NEW.dataset_example_id
                      AND business_id = NEW.business_id
                      AND dataset_id = NEW.target_dataset_id
                ) THEN RAISE EXCEPTION 'invalid candidate dataset example';
                END IF;
                RETURN NEW;
            END; $$;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_dataset_candidates_tenant_integrity "
            "BEFORE INSERT OR UPDATE ON dataset_candidates "
            "FOR EACH ROW EXECUTE FUNCTION beoos_assert_learning_tenant()"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS trg_dataset_candidates_tenant_integrity "
            "ON dataset_candidates"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_learning_tenant()"))
    op.drop_table("improvement_suggestions")
    op.drop_table("dataset_candidates")
