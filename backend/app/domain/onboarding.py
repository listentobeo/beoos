from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ResponseSource = Literal[
    "user", "website_inferred", "connector_inferred", "imported", "system"
]


class OnboardingStart(BaseModel):
    selected_first_problem: str | None = Field(default=None, max_length=120)


class OnboardingAnswer(BaseModel):
    question_key: str = Field(min_length=2, max_length=160)
    workflow_key: str | None = Field(default=None, max_length=160)
    response_type: Literal["text", "choice", "list", "object", "examples", "skipped"]
    response_value: dict[str, Any] = Field(default_factory=dict)
    source: ResponseSource = "user"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    skip_explanation: str | None = Field(default=None, max_length=2_000)


class ConfirmInferredResponse(BaseModel):
    response_id: UUID
    accepted: bool
    replacement_value: dict[str, Any] | None = None


class OnboardingQuestion(BaseModel):
    key: str
    stage: int
    prompt: str
    response_type: str
    required: bool
    help_text: str = ""
    options: list[str] = Field(default_factory=list)


class OnboardingState(BaseModel):
    id: UUID
    business_id: UUID
    stage: int
    status: str
    completion_percentage: int
    selected_first_problem: str | None
    current_question: OnboardingQuestion | None
    pending_confirmations: int
    draft_specification: dict[str, Any]
    deployment_mode: str
