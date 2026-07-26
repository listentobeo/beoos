from pathlib import Path

from app.infrastructure.models import (
    OperatorConversation,
    OperatorMessage,
    OperatorTurn,
    Role,
)
from app.services.operator import (
    MAX_TOOL_CALLS,
    OPERATOR_TOOL_REGISTRY,
    model_selected_operator_tools,
    route_operator_tools,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260726_0024_controlled_operator.py"


def test_operator_tool_routing_is_bounded_and_deterministic() -> None:
    selected = route_operator_tools(
        "Why did the pricing workflow fail and what revenue did it influence?",
        "analytics",
        Role.viewer,
    )
    assert len(selected) <= MAX_TOOL_CALLS
    assert "read_business_profile" in selected
    assert "read_official_pricing" in selected
    assert "read_traces_and_failures" in selected
    assert all(item in OPERATOR_TOOL_REGISTRY for item in selected)


def test_viewer_cannot_receive_propose_tools() -> None:
    selected = route_operator_tools("Start a workflow and send an email", "general", Role.viewer)
    assert "start_workflow" not in selected
    assert "propose_approval" not in selected
    assert not any("send" in item for item in OPERATOR_TOOL_REGISTRY)


def test_model_selection_cannot_escape_deterministic_candidates() -> None:
    selected = model_selected_operator_tools(
        ["read_marketing_metrics", "start_workflow", "arbitrary_shell"],
        ["read_business_profile", "read_marketing_metrics"],
        Role.viewer,
    )
    assert selected == ["read_business_profile", "read_marketing_metrics"]


def test_operator_history_is_non_authoritative_and_tenant_scoped() -> None:
    assert OperatorConversation.__tablename__ == "operator_conversations"
    assert OperatorMessage.__tablename__ == "operator_messages"
    assert OperatorTurn.__tablename__ == "operator_turns"
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "NOT authoritative" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "cross-tenant operator conversation" in migration
    assert "tool_call_count >= 0 AND tool_call_count <= max_tool_calls" in migration
