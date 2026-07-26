from decimal import Decimal
from statistics import median
from typing import Any


def ratio(numerator: int | Decimal, denominator: int | Decimal) -> Decimal | None:
    if not denominator:
        return None
    return Decimal(numerator) / Decimal(denominator)


def median_minutes(values: list[Decimal]) -> Decimal | None:
    return Decimal(median(values)) if values else None


def metric(
    key: str,
    value: Decimal | int | None,
    *,
    unit: str,
    source: str = "measured",
    baseline: Decimal | None = None,
) -> dict[str, Any]:
    improvement = None
    if baseline is not None and value is not None and baseline != 0:
        improvement = (baseline - Decimal(value)) / baseline
    return {
        "key": key,
        "value": str(value) if value is not None else None,
        "unit": unit,
        "source": source,
        "baseline": str(baseline) if baseline is not None else None,
        "improvement": str(improvement) if improvement is not None else None,
    }
