from decimal import Decimal

from app.infrastructure.models import Role
from app.services.evaluation_runner import aggregate_metrics
from app.services.failure_recovery import classify_failure, retry_delay
from app.services.operator import route_operator_tools


def test_duplicate_timeout_unknown_and_permanent_failure_policies() -> None:
    assert classify_failure(ValueError("duplicate event")) == "validation"
    assert classify_failure(TimeoutError()) == "timeout"
    assert (
        classify_failure(ConnectionError(), external_state_uncertain=True)
        == "external_action_unknown"
    )
    assert retry_delay("external_action_unknown", 1) is None
    assert retry_delay("permanent_failure", 1) is None


def test_evaluation_aggregation_handles_large_dataset_deterministically() -> None:
    rows = [
        {
            "pass_fail": True,
            "scores": {
                "output_schema_validity": True,
                "classification_accuracy": Decimal("1"),
                "price_safety": True,
                "prohibited_promise_safety": True,
                "required_escalation": True,
            },
        }
        for _ in range(10_000)
    ]
    metrics = aggregate_metrics(rows)
    assert metrics["overall_pass_rate"] == Decimal("1")
    assert metrics["unsafe_pricing_error_rate"] == Decimal("0")


def test_operator_routing_remains_bounded_across_many_tenants() -> None:
    for index in range(5_000):
        selected = route_operator_tools(
            f"tenant {index}: pricing marketing CRM workflow errors and revenue",
            "general",
            Role.viewer,
        )
        assert 1 <= len(selected) <= 4
