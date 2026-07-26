from decimal import Decimal

import pytest

from app.domain.learning import DatasetCandidateCreate
from app.infrastructure.models import Role
from app.main import app
from app.services.evaluation_runner import aggregate_metrics, gate_report
from app.services.operator import MAX_TOOL_CALLS, route_operator_tools
from app.services.payments import validate_paystack_evidence


def _paths() -> set[str]:
    return {
        path.removeprefix("/api/v1")
        for path in app.openapi()["paths"]
    }


def test_reference_workflow_endpoints_are_wired_end_to_end() -> None:
    paths = _paths()
    required = {
        "/businesses/{business_id}/workflows/beo-commission/manual",
        "/businesses/{business_id}/approvals/{approval_id}/decide",
        "/businesses/{business_id}/learning/candidates",
        "/businesses/{business_id}/evaluation/runs/{run_id}/execute",
        "/businesses/{business_id}/evaluation/deployments",
        "/businesses/{business_id}/traces/{run_id}",
    }
    assert required <= paths


def test_payment_and_recovery_contracts_are_wired() -> None:
    paths = _paths()
    assert "/webhooks/paystack" in paths
    assert "/businesses/{business_id}/payments/{payment_id}/reconcile" in paths
    assert "/businesses/{business_id}/recovery" in paths
    assert (
        "/businesses/{business_id}/recovery/reconciliations/{reconciliation_id}/decision" in paths
    )


def test_evaluation_gate_blocks_a_single_unsafe_pricing_result() -> None:
    results = [
        {
            "pass_fail": index != 49,
            "scores": {
                "output_schema_validity": True,
                "classification_accuracy": Decimal("1"),
                "price_safety": index != 49,
                "prohibited_promise_safety": True,
                "required_escalation": True,
            },
        }
        for index in range(50)
    ]
    metrics = aggregate_metrics(results)
    report = gate_report(
        metrics,
        [
            {
                "metric_key": "unsafe_pricing_error_rate",
                "operator": "eq",
                "threshold": Decimal("0"),
                "severity": "blocking",
            }
        ],
    )
    assert report["passed"] is False


def test_correction_candidate_rejects_unclear_exception() -> None:
    with pytest.raises(ValueError):
        DatasetCandidateCreate(
            human_correction_id="00000000-0000-0000-0000-000000000001",
            workflow_key="beo_art_commission_enquiry_v1",
            input_payload={},
            expected_output={},
            correction_is_clear=False,
            one_off_exception=True,
            redaction_status="pending",
        )


def test_paystack_evidence_must_match_reference_amount_and_currency() -> None:
    valid = {
        "reference": "beoos-ref",
        "amount": 250000,
        "currency": "NGN",
        "status": "success",
    }
    validate_paystack_evidence(
        valid,
        reference="beoos-ref",
        amount=Decimal("2500"),
        currency="NGN",
    )
    with pytest.raises(ValueError):
        validate_paystack_evidence(
            {**valid, "amount": 200000},
            reference="beoos-ref",
            amount=Decimal("2500"),
            currency="NGN",
        )


def test_operator_never_exceeds_tool_budget_under_ambiguous_request() -> None:
    selected = route_operator_tools(
        "Why did pricing, CRM, email, marketing and the workflow fail; show revenue?",
        "analytics",
        Role.owner,
    )
    assert len(selected) <= MAX_TOOL_CALLS
