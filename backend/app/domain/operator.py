from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

OperatorMode = Literal[
    "general",
    "inbox",
    "crm",
    "quotes",
    "pricing",
    "marketing",
    "analytics",
]

OperatorActionKind = Literal[
    "read_only",
    "needs_confirmation",
    "future_tool",
]


class OperatorChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=4000)
    mode: OperatorMode = "general"
    conversation_context: list[dict[str, str]] = Field(default_factory=list, max_length=10)
    conversation_id: UUID | None = None


class OperatorActionSuggestion(BaseModel):
    label: str
    kind: OperatorActionKind
    reason: str
    tool_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class OperatorChatResponse(BaseModel):
    success: bool = True
    answer: str
    summary: list[str] = Field(default_factory=list)
    recommended_actions: list[OperatorActionSuggestion] = Field(default_factory=list)
    read_only_tools_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    conversation_id: UUID | None = None
    grounding_sources: list[dict[str, Any]] = Field(default_factory=list)
    statement_labels: list[dict[str, str]] = Field(default_factory=list)
    execution: dict[str, Any] = Field(default_factory=dict)


class OperatorWorkflowStart(BaseModel):
    workflow_definition_id: UUID
    trigger_reference_type: str = Field(min_length=2, max_length=80)
    trigger_reference_id: str = Field(min_length=1, max_length=255)
    correlation_id: str = Field(min_length=2, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperatorApprovalProposal(BaseModel):
    workflow_run_id: UUID
    workflow_step_id: UUID
    proposed_action_type: str = Field(min_length=2, max_length=120)
    proposed_action_payload: dict[str, Any]
    reason: str = Field(min_length=3, max_length=10_000)
    decision_summary: str = Field(default="", max_length=10_000)
    risk_level: Literal["low", "medium", "high", "critical"]
    required_role: Literal["owner", "admin", "manager"]
    requested_tool_id: UUID | None = None
