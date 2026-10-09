"""Add the tenant-scoped controlled workflow execution model.

Revision ID: 20260723_0014
Revises: 20260723_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0014"
down_revision: str | None = "20260723_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())

TENANT_TABLES = (
    "workflow_runs",
    "workflow_steps",
    "ai_executions",
    "tool_permissions",
    "tool_calls",
    "approval_requests",
    "human_corrections",
    "outcomes",
)


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id")),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("business_objective", sa.Text(), nullable=False),
        sa.Column("workflow_type", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("trigger_type", sa.String(80), nullable=False),
        sa.Column("input_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("configuration", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("policy_version", sa.String(80), nullable=False, server_default="1"),
        sa.Column("prompt_version", sa.String(80), nullable=False, server_default="1"),
        sa.Column(
            "deployment_mode", sa.String(40), nullable=False, server_default="experimental"
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('draft','experimental','shadow','approval_required',"
            "'limited_autonomy','active','archived')",
            name="ck_workflow_definition_status",
        ),
        sa.CheckConstraint(
            "deployment_mode IN ('experimental','shadow','approval_required',"
            "'limited_autonomy','active')",
            name="ck_workflow_definition_deployment_mode",
        ),
    )
    op.create_index(
        "uq_workflow_definitions_tenant_key_version",
        "workflow_definitions",
        ["business_id", "key", "version"],
        unique=True,
    )
    op.create_index(
        "uq_workflow_definitions_global_key_version",
        "workflow_definitions",
        ["key", "version"],
        unique=True,
        postgresql_where=sa.text("business_id IS NULL"),
    )
    op.create_index(
        "ix_workflow_definitions_business_status",
        "workflow_definitions",
        ["business_id", "status"],
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_definition_id",
            UUID,
            sa.ForeignKey("workflow_definitions.id"),
            nullable=False,
        ),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.String(80), nullable=False),
        sa.Column("trigger_reference_type", sa.String(80), nullable=False),
        sa.Column("trigger_reference_id", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("current_step_key", sa.String(120)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error_message_sanitized", sa.Text()),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("initiated_by_user_id", sa.String(255)),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id",
            "workflow_definition_id",
            "idempotency_key",
            name="uq_workflow_run_tenant_definition_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','waiting_for_input','waiting_for_approval',"
            "'retry_scheduled','completed','failed','cancelled')",
            name="ck_workflow_run_status",
        ),
    )
    op.create_index(
        "ix_workflow_runs_business_status", "workflow_runs", ["business_id", "status"]
    )
    op.create_index(
        "ix_workflow_runs_business_created", "workflow_runs", ["business_id", "created_at"]
    )
    op.create_index(
        "ix_workflow_runs_correlation", "workflow_runs", ["business_id", "correlation_id"]
    )

    op.create_table(
        "workflow_steps",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(120), nullable=False),
        sa.Column("step_type", sa.String(40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("input_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message_sanitized", sa.Text()),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.UniqueConstraint("workflow_run_id", "step_key", "sequence"),
        sa.CheckConstraint(
            "step_type IN ('deterministic','ai_judgment','tool_call','validation',"
            "'approval','wait','outcome')",
            name="ck_workflow_step_type",
        ),
    )
    op.create_index(
        "ix_workflow_steps_business_status", "workflow_steps", ["business_id", "status"]
    )
    op.create_index(
        "ix_workflow_steps_run_sequence", "workflow_steps", ["workflow_run_id", "sequence"]
    )

    op.create_table(
        "ai_executions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_id",
            UUID,
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_key", sa.String(120), nullable=False),
        sa.Column("agent_version", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("input_schema_version", sa.String(80), nullable=False),
        sa.Column("output_schema_version", sa.String(80), nullable=False),
        sa.Column(
            "context_references", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("structured_input", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "structured_output", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("provider_response_id", sa.String(255)),
        sa.Column("token_input", sa.Integer()),
        sa.Column("token_output", sa.Integer()),
        sa.Column("estimated_cost", sa.Numeric(14, 6)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("confidence", sa.Numeric(7, 4)),
        sa.Column("parse_status", sa.String(40), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safety_flags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamps(),
    )
    op.create_index(
        "ix_ai_executions_business_created", "ai_executions", ["business_id", "created_at"]
    )
    op.create_index("ix_ai_executions_run", "ai_executions", ["workflow_run_id"])
    op.create_index(
        "ix_ai_executions_agent_version", "ai_executions", ["agent_key", "agent_version"]
    )

    op.create_table(
        "tool_definitions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(40), nullable=False),
        sa.Column("input_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_external", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_reversible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "requires_approval_by_default", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint("key", "version"),
    )

    op.create_table(
        "tool_permissions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "tool_definition_id", UUID, sa.ForeignKey("tool_definitions.id"), nullable=False
        ),
        sa.Column("workflow_definition_id", UUID, sa.ForeignKey("workflow_definitions.id")),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("permission", sa.String(40), nullable=False),
        sa.Column("constraints", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("approved_by", sa.String(255), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "business_id",
            "tool_definition_id",
            "workflow_definition_id",
            "role",
            name="uq_tool_permission_scope",
        ),
        sa.CheckConstraint(
            "permission IN ('read','propose','execute')", name="ck_tool_permission"
        ),
    )
    op.create_index("ix_tool_permissions_business", "tool_permissions", ["business_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_id",
            UUID,
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tool_definition_id", UUID, sa.ForeignKey("tool_definitions.id"), nullable=False
        ),
        sa.Column(
            "permission_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "request_payload_sanitized",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("request_hash", sa.String(96), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "response_payload_sanitized",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("external_reference", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message_sanitized", sa.Text()),
        *_timestamps(),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_tool_call_idempotency"),
    )
    op.create_index("ix_tool_calls_business_status", "tool_calls", ["business_id", "status"])
    op.create_index("ix_tool_calls_run", "tool_calls", ["workflow_run_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_id",
            UUID,
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proposed_action_type", sa.String(120), nullable=False),
        sa.Column(
            "proposed_action_payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "context_references", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("confidence", sa.Numeric(7, 4)),
        sa.Column("risk_level", sa.String(40), nullable=False),
        sa.Column("affected_customer_id", UUID, sa.ForeignKey("contacts.id")),
        sa.Column("financial_impact", sa.Numeric(14, 2)),
        sa.Column("requested_tool_id", UUID, sa.ForeignKey("tool_definitions.id")),
        sa.Column("required_role", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("decided_by", sa.String(255)),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("original_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("final_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("execution_status", sa.String(40)),
        sa.Column("execution_reference", sa.String(255)),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('pending','approved','edited','rejected','expired','cancelled')",
            name="ck_approval_request_status",
        ),
    )
    op.create_index(
        "ix_approval_requests_business_status", "approval_requests", ["business_id", "status"]
    )
    op.create_index("ix_approval_requests_run", "approval_requests", ["workflow_run_id"])
    op.create_index("ix_approval_requests_expiry", "approval_requests", ["status", "expires_at"])

    op.create_table(
        "human_corrections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ai_execution_id", UUID, sa.ForeignKey("ai_executions.id")),
        sa.Column("approval_request_id", UUID, sa.ForeignKey("approval_requests.id")),
        sa.Column("correction_type", sa.String(60), nullable=False),
        sa.Column("original_value", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("corrected_value", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("corrected_by", sa.String(255), nullable=False),
        sa.Column("approved_for_dataset", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_index(
        "ix_human_corrections_business_created",
        "human_corrections",
        ["business_id", "created_at"],
    )
    op.create_index("ix_human_corrections_run", "human_corrections", ["workflow_run_id"])

    op.create_table(
        "outcomes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "workflow_run_id",
            UUID,
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("value_numeric", sa.Numeric(18, 4)),
        sa.Column("value_currency", sa.String(3)),
        sa.Column("value_text", sa.Text()),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("recorded_by", sa.String(255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.Numeric(7, 4)),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
    )
    op.create_index("ix_outcomes_business_type", "outcomes", ["business_id", "outcome_type"])
    op.create_index(
        "ix_outcomes_business_observed", "outcomes", ["business_id", "observed_at"]
    )
    op.create_index("ix_outcomes_run", "outcomes", ["workflow_run_id"])

    op.execute(sa.text("ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            "CREATE POLICY beoos_workflow_definition_read ON workflow_definitions FOR SELECT "
            "USING (business_id IS NULL OR beoos_can_access_business(business_id))"
        )
    )
    op.execute(
        sa.text(
            "CREATE POLICY beoos_workflow_definition_write ON workflow_definitions "
            "FOR ALL USING (business_id IS NOT NULL AND beoos_can_access_business(business_id)) "
            "WITH CHECK (business_id IS NOT NULL AND beoos_can_access_business(business_id))"
        )
    )
    for table_name in TENANT_TABLES:
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
            CREATE OR REPLACE FUNCTION beoos_assert_workflow_tenant()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE related_business_id uuid;
            BEGIN
                IF TG_TABLE_NAME = 'workflow_runs' THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                    IF related_business_id IS NOT NULL
                       AND related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant workflow definition';
                    END IF;
                ELSIF TG_TABLE_NAME IN (
                    'workflow_steps','ai_executions','tool_calls','approval_requests',
                    'human_corrections','outcomes'
                ) THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_runs WHERE id = NEW.workflow_run_id;
                    IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant workflow run relationship';
                    END IF;
                    IF TG_TABLE_NAME = 'approval_requests' THEN
                        IF NEW.affected_customer_id IS NOT NULL THEN
                            SELECT business_id INTO related_business_id
                            FROM contacts WHERE id = NEW.affected_customer_id;
                            IF related_business_id IS DISTINCT FROM NEW.business_id THEN
                                RAISE EXCEPTION 'cross-tenant approval customer';
                            END IF;
                        END IF;
                    END IF;
                ELSIF TG_TABLE_NAME = 'tool_permissions'
                      AND NEW.workflow_definition_id IS NOT NULL THEN
                    SELECT business_id INTO related_business_id
                    FROM workflow_definitions WHERE id = NEW.workflow_definition_id;
                    IF related_business_id IS NULL
                       OR related_business_id IS DISTINCT FROM NEW.business_id THEN
                        RAISE EXCEPTION 'cross-tenant tool permission workflow';
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    for table_name in TENANT_TABLES:
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_{table_name}_tenant_integrity "
                f"BEFORE INSERT OR UPDATE ON {table_name} "
                "FOR EACH ROW EXECUTE FUNCTION beoos_assert_workflow_tenant()"
            )
        )


def downgrade() -> None:
    for table_name in TENANT_TABLES:
        op.execute(
            sa.text(
                f"DROP TRIGGER IF EXISTS trg_{table_name}_tenant_integrity ON {table_name}"
            )
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS beoos_assert_workflow_tenant()"))
    op.drop_table("outcomes")
    op.drop_table("human_corrections")
    op.drop_table("approval_requests")
    op.drop_table("tool_calls")
    op.drop_table("tool_permissions")
    op.drop_table("tool_definitions")
    op.drop_table("ai_executions")
    op.drop_table("workflow_steps")
    op.drop_table("workflow_runs")
    op.drop_table("workflow_definitions")


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
