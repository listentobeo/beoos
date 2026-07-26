from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "database" / "migrations" / "versions"

TENANT_TABLES = {
    "evaluation_thresholds": "20260726_0020_evaluation_deployment_gates.py",
    "workflow_deployments": "20260726_0020_evaluation_deployment_gates.py",
    "dataset_candidates": "20260726_0021_controlled_learning.py",
    "improvement_suggestions": "20260726_0021_controlled_learning.py",
    "workflow_value_baselines": "20260726_0022_workflow_value_baselines.py",
    "marketing_opportunities": "20260726_0023_marketing_experiments.py",
    "marketing_experiments": "20260726_0023_marketing_experiments.py",
    "operator_conversations": "20260726_0024_controlled_operator.py",
    "operator_messages": "20260726_0024_controlled_operator.py",
    "operator_turns": "20260726_0024_controlled_operator.py",
    "external_action_reconciliations": "20260726_0025_failure_reconciliation.py",
    "payment_transactions": "20260726_0026_paystack_transactions.py",
    "payment_webhook_events": "20260726_0026_paystack_transactions.py",
}


def test_every_phase_11_to_17_tenant_table_enables_rls() -> None:
    for table, filename in TENANT_TABLES.items():
        migration = (MIGRATIONS / filename).read_text(encoding="utf-8")
        assert table in migration
        assert "ENABLE ROW LEVEL SECURITY" in migration


def test_cross_tenant_integrity_triggers_cover_relationships() -> None:
    combined = "\n".join(
        (MIGRATIONS / filename).read_text(encoding="utf-8")
        for filename in sorted(set(TENANT_TABLES.values()))
    )
    expected = {
        "beoos_assert_deployment_tenant",
        "beoos_assert_learning_tenant",
        "beoos_assert_marketing_experiment_tenant",
        "beoos_assert_operator_tenant",
        "beoos_assert_reconciliation_tenant",
        "beoos_assert_payment_tenant",
    }
    assert all(trigger in combined for trigger in expected)


def test_global_dataset_write_policy_remains_tenant_denied() -> None:
    migration = (MIGRATIONS / "20260724_0019_evaluation_datasets.py").read_text(encoding="utf-8")
    assert "business_id IS NOT NULL AND beoos_can_access_business" in migration
    assert "business_id IS NULL OR beoos_can_access_business" in migration
