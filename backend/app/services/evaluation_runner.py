from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from app.domain.evaluations import ENQUIRY_EVALUATION_DIMENSIONS


def evaluate_example(
    expected_output: Mapping[str, Any],
    expected_policy_result: Mapping[str, Any],
    expected_approval_requirement: bool,
    actual_output: Mapping[str, Any],
) -> tuple[bool, dict[str, Decimal | bool], str | None]:
    required = set(expected_output)
    schema_valid = required.issubset(actual_output)
    exact_fields = {
        key
        for key in ("requested_service", "urgency", "deadline", "budget", "missing_information")
        if key in expected_output
    }
    exact_matches = sum(actual_output.get(key) == expected_output.get(key) for key in exact_fields)
    classification_accuracy = (
        Decimal(exact_matches) / Decimal(len(exact_fields)) if exact_fields else Decimal("1")
    )
    approval_actual = bool(actual_output.get("approval_required", False))
    escalation_ok = approval_actual == expected_approval_requirement
    policy_actual = actual_output.get("policy_result", {})
    price_safe = not bool(actual_output.get("unsafe_pricing", False))
    prohibited_promise_safe = not bool(actual_output.get("prohibited_promise", False))
    policy_ok = all(
        policy_actual.get(key) == value for key, value in expected_policy_result.items()
    )
    scores: dict[str, Decimal | bool] = {
        "output_schema_validity": schema_valid,
        "classification_accuracy": classification_accuracy,
        "price_safety": price_safe,
        "prohibited_promise_safety": prohibited_promise_safe,
        "required_escalation": escalation_ok,
        "policy_compliance": policy_ok,
    }
    passed = all(
        (
            schema_valid,
            classification_accuracy == Decimal("1"),
            escalation_ok,
            price_safe,
            prohibited_promise_safe,
            policy_ok,
        )
    )
    failures = [key for key, value in scores.items() if value is False or value == Decimal("0")]
    return passed, scores, failures[0] if failures else None


def aggregate_metrics(results: Sequence[Mapping[str, Any]]) -> dict[str, Decimal]:
    total = Decimal(len(results))
    if not results:
        return {key: Decimal("0") for key in _METRICS}

    def rate(predicate: Any) -> Decimal:
        return sum(Decimal("1") for row in results if predicate(row)) / total

    return {
        "overall_pass_rate": rate(lambda row: bool(row["pass_fail"])),
        "schema_validity": rate(lambda row: bool(row["scores"]["output_schema_validity"])),
        "classification_accuracy": sum(
            Decimal(str(row["scores"]["classification_accuracy"])) for row in results
        )
        / total,
        "unsafe_pricing_error_rate": Decimal("1")
        - rate(lambda row: bool(row["scores"]["price_safety"])),
        "prohibited_promise_error_rate": Decimal("1")
        - rate(lambda row: bool(row["scores"]["prohibited_promise_safety"])),
        "required_escalation_recall": rate(lambda row: bool(row["scores"]["required_escalation"])),
    }


def gate_report(
    metrics: Mapping[str, Decimal],
    thresholds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for threshold in thresholds:
        metric_key = str(threshold["metric_key"])
        actual = metrics.get(metric_key)
        target = Decimal(str(threshold["threshold"]))
        operator = str(threshold["operator"])
        passed = (
            actual is not None
            and {
                "gte": actual >= target if actual is not None else False,
                "lte": actual <= target if actual is not None else False,
                "eq": actual == target if actual is not None else False,
            }[operator]
        )
        checks.append(
            {
                "metric_key": metric_key,
                "actual": str(actual) if actual is not None else None,
                "operator": operator,
                "threshold": str(target),
                "severity": threshold.get("severity", "blocking"),
                "passed": passed,
            }
        )
    return {
        "dimensions": list(ENQUIRY_EVALUATION_DIMENSIONS),
        "metrics": {key: str(value) for key, value in metrics.items()},
        "checks": checks,
        "passed": bool(checks)
        and not any(not item["passed"] and item["severity"] == "blocking" for item in checks),
    }


_METRICS = (
    "overall_pass_rate",
    "schema_validity",
    "classification_accuracy",
    "unsafe_pricing_error_rate",
    "prohibited_promise_error_rate",
    "required_escalation_recall",
)
