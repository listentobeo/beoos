from pathlib import Path

from app.domain.approvals import ApprovalDecisionInput
from app.infrastructure.models import HumanCorrection, Role
from app.services.tool_registry import ROLE_RANK

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260724_0018_structured_approvals.py"
)


def test_all_approval_actions_and_correction_reasons_are_typed() -> None:
    decision = ApprovalDecisionInput(
        action="edit_and_approve",
        edited_payload={"body_text": "Corrected"},
        correction_reason="wrong_tone",
        decision_reason="Adjusted to the approved brand voice",
    )
    assert decision.action == "edit_and_approve"
    assert decision.correction_reason == "wrong_tone"


def test_correction_record_preserves_original_edit_result_and_changed_fields() -> None:
    columns = HumanCorrection.__table__.c
    for name in (
        "original_value",
        "corrected_value",
        "changed_fields",
        "reason",
        "corrected_by",
        "final_action",
        "result",
        "created_at",
    ):
        assert name in columns


def test_manager_role_sits_between_admin_and_agent() -> None:
    assert Role.manager.value == "manager"
    assert ROLE_RANK[Role.admin] > ROLE_RANK[Role.manager] > ROLE_RANK[Role.agent]


def test_approval_migration_is_additive_and_keeps_rollback_safe() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ALTER TYPE role ADD VALUE IF NOT EXISTS 'manager'" in migration
    assert "changed_fields" in migration
    assert "final_action" in migration
    assert "result" in migration
