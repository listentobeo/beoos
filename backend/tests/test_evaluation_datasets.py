from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.evaluations import (
    ENQUIRY_EVALUATION_DIMENSIONS,
    DatasetExampleCreate,
    EvaluationResultCreate,
)
from app.infrastructure.models import (
    Dataset,
    DatasetExample,
    EvaluationResult,
    EvaluationRun,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260724_0019_evaluation_datasets.py"
)


def test_evaluation_models_capture_required_records() -> None:
    assert Dataset.__tablename__ == "datasets"
    assert DatasetExample.__tablename__ == "dataset_examples"
    assert EvaluationRun.__tablename__ == "evaluation_runs"
    assert EvaluationResult.__tablename__ == "evaluation_results"
    assert Dataset.__table__.c.business_id.nullable is True
    assert EvaluationRun.__table__.c.business_id.nullable is False
    assert EvaluationResult.__table__.c.business_id.nullable is False


def test_initial_enquiry_dimensions_are_complete() -> None:
    assert set(ENQUIRY_EVALUATION_DIMENSIONS) == {
        "service_classification",
        "urgency",
        "deadline_extraction",
        "budget_extraction",
        "missing_information_detection",
        "policy_compliance",
        "price_safety",
        "prohibited_promise_detection",
        "approval_requirement",
        "tone",
        "factual_grounding",
        "output_schema_validity",
    }


def test_personal_data_cannot_skip_redaction_review() -> None:
    with pytest.raises(ValidationError):
        DatasetExampleCreate(
            source_type="manual",
            source_reference="example-1",
            input_payload={},
            expected_output={},
            expected_policy_result={},
            expected_approval_requirement=False,
            difficulty="medium",
            contains_personal_data=True,
            redaction_status="not_required",
        )


def test_human_evaluation_requires_human_review_flag() -> None:
    with pytest.raises(ValidationError):
        EvaluationResultCreate(
            dataset_example_id="00000000-0000-0000-0000-000000000001",
            actual_output={},
            pass_fail=True,
            scores={},
            evaluator_type="human",
            human_reviewed=False,
        )


def test_evaluation_migration_enforces_global_read_tenant_write_and_integrity() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for table_name in (
        "datasets",
        "dataset_examples",
        "evaluation_runs",
        "evaluation_results",
    ):
        assert table_name in migration
    assert "business_id IS NULL OR beoos_can_access_business" in migration
    assert "business_id IS NOT NULL AND beoos_can_access_business" in migration
    assert "beoos_assert_evaluation_tenant" in migration
    assert "evaluation example is outside run dataset" in migration
