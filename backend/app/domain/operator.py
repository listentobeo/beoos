from typing import Any, Literal

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
