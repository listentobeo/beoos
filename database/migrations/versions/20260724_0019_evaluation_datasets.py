"""Add tenant-scoped evaluation datasets and runs.

Revision ID: 20260724_0019
Revises: 20260724_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260724_0019"
down_revision: str | None = "20260724_0018"
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
        "datasets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE")
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("workflow_key", sa.String(160), nullable=False),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "scope IN ('global','industry','tenant')", name="ck_dataset_scope"
        ),
        sa.CheckConstraint(
            "(scope = 'global' AND business_id IS NULL) OR "
            "(scope IN ('industry','tenant') AND business_id IS NOT NULL)",
            name="ck_dataset_scope_business",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','archived')", name="ck_dataset_status"
        ),
    )
    op.create_index(
        "uq_datasets_tenant_name_version",
        "datasets",
        ["business_id", "name", "version"],
        unique=True,
        postgresql_where=sa.text("business_id IS NOT NULL"),
    )
    op.create_index(
        "uq_datasets_global_name_version",
        "datasets",
        ["name", "version"],
        unique=True,
        postgresql_where=sa.text("business_id IS NULL"),
    )
    op.create_index(
        "ix_datasets_business_workflow", "datasets", ["business_id", "workflow_key"]
    )
    op.create_index("ix_datasets_scope_status", "datasets", ["scope", "status"])

    op.create_table(
        "dataset_examples",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "dataset_id",
            UUID,
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE")
        ),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=False),
        sa.Column("input_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("expected_output", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "expected_policy_result",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("expected_approval_requirement", sa.Boolean(), nullable=False),
        sa.Column("labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("difficulty", sa.String(40), nullable=False),
        sa.Column("contains_personal_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("redaction_status", sa.String(40), nullable=False),
        sa.Column("approved_by", sa.String(255)),
        *_timestamps(),
        sa.CheckConstraint(
            "difficulty IN ('easy','medium','hard','adversarial')",
            name="ck_dataset_example_difficulty",
        ),
        sa.CheckConstraint(
            "redaction_status IN ('not_required','pending','redacted','rejected')",
            name="ck_dataset_example_redaction",
        ),
        sa.CheckConstraint(
            "NOT contains_personal_data OR redaction_status IN ('pending','redacted','rejected')",
            name="ck_dataset_example_personal_data",
        ),
    )
    op.create_index("ix_dataset_examples_dataset", "dataset_examples", ["dataset_id"])
    op.create_index(
        "ix_dataset_examples_business_redaction",
        "dataset_examples",
        ["business_id", "redaction_status"],
    )

    op.create_table(
        "evaluation_runs",
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
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("dataset_id", UUID, sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("dataset_version", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("total_examples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("average_latency", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_evaluation_run_status",
        ),
        sa.CheckConstraint(
            "total_examples >= 0 AND passed >= 0 AND failed >= 0",
            name="ck_evaluation_run_counts",
        ),
    )
    op.create_index(
        "ix_evaluation_runs_business_status", "evaluation_runs", ["business_id", "status"]
    )
    op.create_index(
        "ix_evaluation_runs_workflow_version",
        "evaluation_runs",
        ["workflow_definition_id", "workflow_version"],
    )
    op.create_index(
        "ix_evaluation_runs_dataset_version",
        "evaluation_runs",
        ["dataset_id", "dataset_version"],
    )

    op.create_table(
        "evaluation_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "business_id",
            UUID,
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_example_id",
            UUID,
            sa.ForeignKey("dataset_examples.id"),
            nullable=False,
        ),
        sa.Column("actual_output", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pass_fail", sa.Boolean(), nullable=False),
        sa.Column("scores", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("failure_type", sa.String(80)),
        sa.Column("evaluator_type", sa.String(60), nullable=False),
        sa.Column("evaluator_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "dataset_example_id",
            name="uq_evaluation_result_run_example",
        ),
        sa.CheckConstraint(
            "evaluator_type IN ('exact','rule','schema','human','model_assisted')",
            name="ck_evaluation_result_evaluator",
        ),
    )
    op.create_index(
        "ix_evaluation_results_business_pass",
        "evaluation_results",
        ["business_id", "pass_fail"],
    )
    op.create_index(
        "ix_evaluation_results_run", "evaluation_results", ["evaluation_run_id"]
    )

    op.execute(sa.text("ALTER TABLE datasets ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_dataset_read ON datasets FOR SELECT "
            "USING (business_id IS NULL OR beoos_can_access_business(business_id))"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY beoos_dataset_write ON datasets FOR ALL "
            "USING (business_id IS NOT NULL AND beoos_can_access_business(business_id)) "
            "WITH CHECK (business_id IS NOT NULL AND beoos_can_access_business(business_id))"
        )
    )
    op.execute(sa.text("ALTER TABLE dataset_examples ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_dataset_example_read ON dataset_examples FOR SELECT "
            "USING (business_id IS NULL OR beoos_can_access_business(business_id))"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY beoos_dataset_example_write ON dataset_examples FOR ALL "
            "USING (business_id IS NOT NULL AND beoos_can_access_business(business_id)) "
            "WITH CHECK (business_id IS NOT NULL AND beoos_can_access_business(business_id))"
        )
    )
    for table_name in ("evaluation_runs", "evaluation_results"):
        op.execute(sa.text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"CREATE POLICY beoos_tenant_access ON {table_name} FOR ALL "
                "USING (beoos_can_access_business(business_id)) "
                "WITH CHECK (beoos_can_access_business(business_id))"
            )
        )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION beoos_assert_evaluation_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                related_business_id uuid;
                related_dataset_id uuid;
                related_version integer;
            BEGIN
                IF TG_TABLE_NAME = 'dataset_examples' THEN
                    SELECT business_id INTO related_business_id
                    FROM datasets WHERE id = NEW.dataset_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant dataset example';
                    END IF;
                ELSIF TG_TABLE_NAME = 'evaluation_runs' THEN
                    SELECT business_id, version INTO related_business_id, related_version
                    FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                    IF (related_business_id IS NOT NULL
                        AND related_business_id IS DISTINCT FROM NEW.business_id)
                       OR related_version IS DISTINCT FROM NEW.workflow_version THEN
                        RAISE EXCEPTION 'invalid evaluation workflow reference';
                    END IF;
                    SELECT business_id, version INTO related_business_id, related_version
                    FROM datasets WHERE id = NEW.dataset_id;
                    IF (related_business_id IS NOT NULL
                        AND related_business_id IS DISTINCT FROM NEW.business_id)
                       OR related_version IS DISTINCT FROM NEW.dataset_version THEN
                        RAISE EXCEPTION 'invalid evaluation dataset reference';
                    END IF;
                ELSIF TG_TABLE_NAME = 'evaluation_results' THEN
                    SELECT business_id, dataset_id
                    INTO related_business_id, related_dataset_id
                    FROM evaluation_runs WHERE id = NEW.evaluation_run_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant evaluation result';
                    END IF;
                    SELECT dataset_id INTO related_dataset_id
                    FROM dataset_examples
                    WHERE id = NEW.dataset_example_id
                      AND dataset_id = related_dataset_id;
                    IF related_dataset_id IS NULL THEN
                        RAISE EXCEPTION 'evaluation example is outside run dataset';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    for table_name in ("dataset_examples", "evaluation_runs", "evaluation_results"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table_name}_tenant_integrity "
                f"BEFORE INSERT OR UPDATE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION beoos_assert_evaluation_tenant()"
            )
        )


def downgrade() -> None:
    for table_name in ("dataset_examples", "evaluation_runs", "evaluation_results"):
        op.execute(
            sa.text(f"DROP TRIGGER IF EXISTS trg_{table_name}_tenant_integrity ON {table_name}")
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_evaluation_tenant()"))
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("dataset_examples")
    op.drop_table("datasets")
