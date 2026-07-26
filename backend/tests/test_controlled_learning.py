from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.learning import DatasetCandidateCreate
from app.infrastructure.models import DatasetCandidate, ImprovementSuggestion

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260726_0021_controlled_learning.py"


def _candidate(**overrides: object) -> DatasetCandidateCreate:
    values = {
        "human_correction_id": "00000000-0000-0000-0000-000000000001",
        "workflow_key": "beo_art_commission_enquiry_v1",
        "input_payload": {"message": "redacted"},
        "expected_output": {"reply": "redacted"},
        "correction_is_clear": True,
        "one_off_exception": False,
        "redaction_status": "not_required",
    }
    values.update(overrides)
    return DatasetCandidateCreate(**values)


def test_private_candidate_cannot_bypass_redaction() -> None:
    with pytest.raises(ValidationError):
        _candidate(contains_personal_data=True)


def test_unclear_and_one_off_corrections_are_excluded() -> None:
    with pytest.raises(ValidationError):
        _candidate(correction_is_clear=False)
    with pytest.raises(ValidationError):
        _candidate(one_off_exception=True)


def test_learning_records_are_advisory_and_tenant_scoped() -> None:
    assert DatasetCandidate.__tablename__ == "dataset_candidates"
    assert ImprovementSuggestion.__tablename__ == "improvement_suggestions"
    assert "prompt" not in ImprovementSuggestion.__table__.c
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_assert_learning_tenant" in migration
    assert "invalid dataset candidate correction" in migration
