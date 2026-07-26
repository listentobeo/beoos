from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DatasetCandidateCreate(BaseModel):
    human_correction_id: UUID
    workflow_key: str = Field(min_length=2, max_length=160)
    input_payload: dict[str, Any]
    expected_output: dict[str, Any]
    contains_personal_data: bool = False
    contains_sensitive_data: bool = False
    redaction_status: Literal["not_required", "pending", "redacted"] = "pending"
    correction_is_clear: bool
    one_off_exception: bool = False

    @model_validator(mode="after")
    def enforce_candidate_safety(self) -> "DatasetCandidateCreate":
        if not self.correction_is_clear:
            raise ValueError("Unclear corrections cannot become dataset candidates")
        if self.one_off_exception:
            raise ValueError("One-off exceptions cannot become dataset candidates")
        if (
            self.contains_personal_data or self.contains_sensitive_data
        ) and self.redaction_status == "not_required":
            raise ValueError("Private or sensitive data requires redaction")
        return self


class PrivacyReview(BaseModel):
    approve: bool
    redacted_input: dict[str, Any] | None = None
    redacted_output: dict[str, Any] | None = None
    reason: str = Field(min_length=2, max_length=2_000)

    @model_validator(mode="after")
    def require_redacted_payload(self) -> "PrivacyReview":
        if self.approve and ((self.redacted_input is None) != (self.redacted_output is None)):
            raise ValueError("Redacted input and output must be supplied together")
        return self


class CandidateApproval(BaseModel):
    dataset_id: UUID
    difficulty: Literal["easy", "medium", "hard", "adversarial"] = "medium"
    labels: list[str] = Field(default_factory=list)


class SuggestionDecision(BaseModel):
    status: Literal["accepted_for_review", "dismissed"]
    reason: str = Field(min_length=2, max_length=2_000)
