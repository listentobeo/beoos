from pathlib import Path

from app.infrastructure.models import OnboardingResponse, OnboardingSession
from app.services.onboarding import (
    QUESTIONS,
    build_draft_specification,
    completion,
    connector_disclosures,
    next_question,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260723_0017_progressive_onboarding.py"
)


def test_onboarding_models_are_tenant_scoped_and_resumable() -> None:
    assert OnboardingSession.__table__.c.business_id.nullable is False
    assert OnboardingResponse.__table__.c.business_id.nullable is False
    assert "last_activity_at" in OnboardingSession.__table__.c
    assert "current_question_key" in OnboardingSession.__table__.c
    assert "requires_confirmation" in OnboardingResponse.__table__.c
    assert "confirmed_by" in OnboardingResponse.__table__.c


def test_workspace_basics_stays_short_and_discovery_is_complete() -> None:
    assert len([question for question in QUESTIONS if question.stage == 1]) == 6
    workflow_questions = [question for question in QUESTIONS if question.stage == 4]
    assert len(workflow_questions) == 17
    assert workflow_questions[-1].key == "workflow.never_automate"


def test_onboarding_is_progressive_and_builds_reviewable_draft() -> None:
    first = next_question(set(), "handle_customer_enquiries")
    assert first is not None and first.stage == 1
    stage_one = {question.key for question in QUESTIONS if question.stage == 1}
    assert next_question(stage_one, "handle_customer_enquiries").stage == 2
    assert 0 < completion(stage_one, "handle_customer_enquiries") < 100
    draft = build_draft_specification(
        {
            "workspace.business_name": {"value": "Example Studio"},
            "problem.first": {"value": "handle_customer_enquiries"},
            "examples.cases": {"value": [{"kind": "good", "input": "Need a mural"}]},
        }
    )
    assert draft["status"] == "draft_requires_owner_review"
    assert draft["prompt_generation"] == "prohibited_from_unreviewed_answers"
    assert draft["deployment_mode"] == "experimental"
    assert draft["dataset_candidates"]


def test_connectors_are_limited_to_selected_problem_and_explain_controls() -> None:
    connectors = connector_disclosures("marketing_opportunities")
    assert set(connectors) == {"search_console"}
    assert connectors["search_console"]["data_accessed"]
    assert connectors["search_console"]["approval_required"]
    assert connectors["search_console"]["disconnect"]


def test_onboarding_migration_has_rls_and_cross_tenant_guard() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "onboarding_sessions" in migration
    assert "onboarding_responses" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_assert_onboarding_tenant" in migration
