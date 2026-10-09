from typing import Literal

from pydantic import BaseModel, Field

FailureCategory = Literal[
    "authentication",
    "authorization",
    "validation",
    "rate_limit",
    "timeout",
    "provider_unavailable",
    "malformed_output",
    "missing_context",
    "duplicate_event",
    "external_action_unknown",
    "payment_pending",
    "permanent_failure",
    "human_timeout",
]


class RecoveryDecision(BaseModel):
    action: Literal["retry", "cancel", "mark_reconciled", "mark_failed"]
    reason: str = Field(min_length=3, max_length=2_000)
    provider_reference: str | None = Field(default=None, max_length=255)


class JobRecoveryDecision(BaseModel):
    action: Literal["retry", "cancel"]
    reason: str = Field(min_length=3, max_length=2_000)
