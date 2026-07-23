from datetime import timedelta

from app.infrastructure.models import DurableJob
from app.services.durable_jobs import _backoff, _sanitized_error


def test_durable_job_is_tenant_scoped_and_idempotent() -> None:
    assert DurableJob.__table__.c.business_id.nullable is False
    constraints = {constraint.name for constraint in DurableJob.__table__.constraints}
    assert "uq_durable_job_idempotency" in constraints


def test_retry_backoff_is_exponential_and_capped() -> None:
    assert _backoff(1) == timedelta(seconds=5)
    assert _backoff(2) == timedelta(seconds=10)
    assert _backoff(20) == timedelta(seconds=900)


def test_errors_are_sanitized_and_bounded() -> None:
    result = _sanitized_error(RuntimeError("x" * 1000))
    assert result.startswith("RuntimeError:")
    assert len(result) <= 514

