from pathlib import Path

from app.infrastructure.models import (
    AIExecution,
    ApprovalRequest,
    HumanCorrection,
    Outcome,
    ToolCall,
    ToolDefinition,
    ToolPermission,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStep,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260723_0014_workflow_core.py"


def test_controlled_workflow_tables_are_registered() -> None:
    assert {
        WorkflowDefinition.__tablename__,
        WorkflowRun.__tablename__,
        WorkflowStep.__tablename__,
        AIExecution.__tablename__,
        ToolDefinition.__tablename__,
        ToolPermission.__tablename__,
        ToolCall.__tablename__,
        ApprovalRequest.__tablename__,
        HumanCorrection.__tablename__,
        Outcome.__tablename__,
    } == {
        "workflow_definitions",
        "workflow_runs",
        "workflow_steps",
        "ai_executions",
        "tool_definitions",
        "tool_permissions",
        "tool_calls",
        "approval_requests",
        "human_corrections",
        "outcomes",
    }


def test_every_tenant_workflow_table_has_non_nullable_business_id() -> None:
    for model in (
        WorkflowRun,
        WorkflowStep,
        AIExecution,
        ToolPermission,
        ToolCall,
        ApprovalRequest,
        HumanCorrection,
        Outcome,
    ):
        assert model.__table__.c.business_id.nullable is False


def test_workflow_security_migration_has_rls_and_integrity_checks() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for table_name in (
        "workflow_definitions",
        "workflow_runs",
        "workflow_steps",
        "ai_executions",
        "tool_permissions",
        "tool_calls",
        "approval_requests",
        "human_corrections",
        "outcomes",
    ):
        assert table_name in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_assert_workflow_tenant" in migration
    assert "business_id IS NULL OR beoos_can_access_business" in migration


def test_external_action_records_have_idempotency_and_request_hash() -> None:
    assert "idempotency_key" in ToolCall.__table__.c
    assert "request_hash" in ToolCall.__table__.c
    assert "permission_snapshot" in ToolCall.__table__.c

