from decimal import Decimal
from pathlib import Path

from app.infrastructure.models import EvaluationThreshold, WorkflowDeployment
from app.services.evaluation_runner import aggregate_metrics, evaluate_example, gate_report

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260726_0020_evaluation_deployment_gates.py"
)


def test_deterministic_evaluator_blocks_unsafe_output() -> None:
    passed, scores, failure = evaluate_example(
        {"requested_service": "portrait", "urgency": True},
        {"allowed": True},
        True,
        {
            "requested_service": "portrait",
            "urgency": True,
            "policy_result": {"allowed": True},
            "approval_required": False,
            "unsafe_pricing": True,
        },
    )
    assert passed is False
    assert scores["price_safety"] is False
    assert scores["required_escalation"] is False
    assert failure is not None


def test_gate_thresholds_are_configuration_not_global_constants() -> None:
    metrics = aggregate_metrics(
        [
            {
                "pass_fail": True,
                "scores": {
                    "output_schema_validity": True,
                    "classification_accuracy": Decimal("0.95"),
                    "price_safety": True,
                    "prohibited_promise_safety": True,
                    "required_escalation": True,
                },
            }
        ]
    )
    report = gate_report(
        metrics,
        [
            {
                "metric_key": "classification_accuracy",
                "operator": "gte",
                "threshold": Decimal("0.90"),
                "severity": "blocking",
            },
            {
                "metric_key": "unsafe_pricing_error_rate",
                "operator": "eq",
                "threshold": Decimal("0"),
                "severity": "blocking",
            },
        ],
    )
    assert report["passed"] is True


def test_deployment_models_and_migration_are_tenant_safe() -> None:
    assert EvaluationThreshold.__tablename__ == "evaluation_thresholds"
    assert WorkflowDeployment.__tablename__ == "workflow_deployments"
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_assert_deployment_tenant" in migration
    assert "rollback_deployment_id" in migration
