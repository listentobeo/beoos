from pathlib import Path

from app.infrastructure.models import ExternalActionReconciliation, ToolCall
from app.services.failure_recovery import classify_failure, recovery_message, retry_delay

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database" / "migrations" / "versions" / "20260726_0025_failure_reconciliation.py"
)


def test_failure_categories_and_unknown_state_policy() -> None:
    assert classify_failure(TimeoutError()) == "timeout"
    assert (
        classify_failure(TimeoutError(), external_state_uncertain=True) == "external_action_unknown"
    )
    assert retry_delay("external_action_unknown", 1) is None
    assert "Do not retry" in recovery_message("external_action_unknown")


def test_retry_policy_is_bounded() -> None:
    assert retry_delay("rate_limit", 1) is not None
    assert retry_delay("rate_limit", 20).total_seconds() <= 1800
    assert retry_delay("validation", 1) is None


def test_reconciliation_model_and_tenant_guards_exist() -> None:
    assert ExternalActionReconciliation.__tablename__ == "external_action_reconciliations"
    assert "failure_category" in ToolCall.__table__.c
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "cross-tenant reconciliation tool call" in migration
