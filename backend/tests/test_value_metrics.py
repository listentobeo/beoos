from decimal import Decimal
from pathlib import Path

from app.infrastructure.models import WorkflowValueBaseline
from app.services.value_metrics import median_minutes, metric, ratio

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database" / "migrations" / "versions" / "20260726_0022_workflow_value_baselines.py"
)


def test_value_helpers_do_not_invent_missing_measurements() -> None:
    assert ratio(1, 0) is None
    assert median_minutes([]) is None
    item = metric("response_time", None, unit="minutes", baseline=Decimal("60"))
    assert item["value"] is None
    assert item["improvement"] is None


def test_measured_improvement_is_compared_to_estimated_baseline() -> None:
    item = metric(
        "response_time",
        Decimal("30"),
        unit="minutes",
        baseline=Decimal("60"),
    )
    assert item["source"] == "measured"
    assert Decimal(item["improvement"]) == Decimal("0.5")


def test_baseline_is_always_labelled_user_estimate_and_tenant_scoped() -> None:
    assert WorkflowValueBaseline.__tablename__ == "workflow_value_baselines"
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "source = 'user_estimate'" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
