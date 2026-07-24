from pathlib import Path

from app.domain.traces import WorkflowTraceDetail

ROOT = Path(__file__).resolve().parents[2]
TRACE_API = ROOT / "backend" / "app" / "api" / "traces.py"


def test_trace_contract_covers_all_operational_sections() -> None:
    assert set(WorkflowTraceDetail.model_fields).issuperset(
        {
            "trigger",
            "customer_and_channel",
            "workflow",
            "business_context_sources",
            "extracted_information",
            "missing_information",
            "ai_operational_summary",
            "policy_checks",
            "deterministic_calculations",
            "tool_calls",
            "approval_decisions",
            "human_edits",
            "external_actions",
            "result",
            "outcomes",
            "estimated_cost",
            "latency_ms",
            "retry_history",
            "errors_and_recovery",
        }
    )


def test_trace_api_supports_required_filters() -> None:
    source = TRACE_API.read_text(encoding="utf-8")
    for filter_name in (
        "business_id",
        "workflow",
        "run_status",
        "channel",
        "customer",
        "date_from",
        "date_to",
        "approval_state",
        "outcome",
        "model",
        "failure_type",
    ):
        assert filter_name in source


def test_trace_never_exposes_hidden_reasoning_fields() -> None:
    fields = set(WorkflowTraceDetail.model_fields)
    assert "chain_of_thought" not in fields
    assert "reasoning_tokens" not in fields
    assert "hidden_reasoning" not in fields
