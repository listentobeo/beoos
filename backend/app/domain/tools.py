from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ToolPermissionUpdate(BaseModel):
    tool_key: str = Field(min_length=2, max_length=120)
    workflow_definition_id: UUID | None = None
    role: Literal["owner", "admin", "manager", "agent", "viewer"]
    permission: Literal["read", "propose", "execute"]
    constraints: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteRequest(BaseModel):
    workflow_run_id: UUID
    workflow_step_id: UUID
    tool_key: str = Field(min_length=2, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=4, max_length=255)
    permission: Literal["read", "propose", "execute"] = "execute"


class ToolView(BaseModel):
    id: UUID
    key: str
    name: str
    description: str
    risk_level: str
    is_external: bool
    is_reversible: bool
    requires_approval_by_default: bool
    enabled: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_role: str
    idempotency_strategy: str
    timeout_seconds: int
    retry_policy: str
    failure_mapping: dict[str, str]
    permissions: list[dict[str, Any]] = Field(default_factory=list)


class ToolCallView(BaseModel):
    id: UUID
    status: str
    tool_key: str
    response: dict[str, Any]
    error_code: str | None
    error_message: str | None
