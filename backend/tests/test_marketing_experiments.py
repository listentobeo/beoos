from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.marketing import MarketingExperimentCreate
from app.infrastructure.models import MarketingExperiment, MarketingOpportunity

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "versions" / "20260726_0023_marketing_experiments.py"


def _experiment(**overrides: object) -> MarketingExperimentCreate:
    now = datetime.now(UTC)
    values = {
        "opportunity_id": "00000000-0000-0000-0000-000000000001",
        "approved_change": "Improve the approved service-page title.",
        "target_page": "https://example.com/portraits",
        "baseline_period_start": now - timedelta(days=30),
        "baseline_period_end": now - timedelta(days=15),
        "comparison_period_start": now,
        "comparison_period_end": now + timedelta(days=15),
        "execution_method": "manual",
    }
    values.update(overrides)
    return MarketingExperimentCreate(**values)


def test_autonomous_marketing_publishing_is_prohibited() -> None:
    with pytest.raises(ValidationError):
        _experiment(publish_automatically=True)


def test_approved_tool_method_requires_tool_provenance() -> None:
    with pytest.raises(ValidationError):
        _experiment(execution_method="approved_tool")


def test_experiment_models_and_tenant_integrity_exist() -> None:
    assert MarketingOpportunity.__tablename__ == "marketing_opportunities"
    assert MarketingExperiment.__tablename__ == "marketing_experiments"
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "cross-tenant marketing opportunity" in migration
    assert "invalid approved marketing tool call" in migration
