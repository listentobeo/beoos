from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ENQUIRY_EVALUATION_DIMENSIONS = (
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
)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10_000)
    workflow_key: str = Field(min_length=2, max_length=160)
    scope: Literal["industry", "tenant"] = "tenant"
    status: Literal["draft", "active"] = "draft"


class DatasetExampleCreate(BaseModel):
    source_type: str = Field(min_length=2, max_length=80)
    source_reference: str = Field(min_length=1, max_length=255)
    input_payload: dict[str, Any]
    expected_output: dict[str, Any]
    expected_policy_result: dict[str, Any]
    expected_approval_requirement: bool
    labels: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard", "adversarial"]
    contains_personal_data: bool = False
    redaction_status: Literal["not_required", "pending", "redacted", "rejected"]

    @model_validator(mode="after")
    def validate_redaction(self) -> "DatasetExampleCreate":
        if self.contains_personal_data and self.redaction_status == "not_required":
            raise ValueError("Personal data requires redaction review")
        return self


class EvaluationRunCreate(BaseModel):
    workflow_definition_id: UUID
    dataset_id: UUID
    model: str = Field(min_length=2, max_length=160)
    prompt_version: str = Field(min_length=1, max_length=80)
    policy_version: str = Field(min_length=1, max_length=80)


class EvaluationResultCreate(BaseModel):
    dataset_example_id: UUID
    actual_output: dict[str, Any]
    pass_fail: bool
    scores: dict[str, Decimal | int | float | bool | str | None]
    failure_type: str | None = Field(default=None, max_length=80)
    evaluator_type: Literal["exact", "rule", "schema", "human", "model_assisted"]
    evaluator_notes: str = Field(default="", max_length=10_000)
    human_reviewed: bool = False

    @model_validator(mode="after")
    def require_human_flag(self) -> "EvaluationResultCreate":
        if self.evaluator_type == "human" and not self.human_reviewed:
            raise ValueError("Human evaluator results must be marked human reviewed")
        return self


class EvaluationExecuteRequest(BaseModel):
    outputs: dict[UUID, dict[str, Any]]
    latencies_ms: dict[UUID, int] = Field(default_factory=dict)
    estimated_costs: dict[UUID, Decimal] = Field(default_factory=dict)


class EvaluationThresholdUpsert(BaseModel):
    metric_key: str = Field(min_length=2, max_length=120)
    operator: Literal["gte", "lte", "eq"] = "gte"
    threshold: Decimal
    severity: Literal["blocking", "warning"] = "blocking"


class DeploymentCreate(BaseModel):
    workflow_definition_id: UUID
    evaluation_run_id: UUID
    deployment_mode: Literal[
        "experimental", "shadow", "approval_required", "limited_autonomy", "active"
    ]


class DeploymentDecision(BaseModel):
    approve: bool
    reason: str = Field(min_length=2, max_length=2_000)
