from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowTraceSummary(BaseModel):
    run_id: UUID
    workflow_key: str
    workflow_name: str
    workflow_version: int
    status: str
    channel: str
    customer_id: UUID | None
    customer_name: str | None
    approval_state: str | None
    outcome_types: list[str]
    model: str | None
    failure_type: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class WorkflowTraceDetail(BaseModel):
    run_id: UUID
    trigger: dict[str, Any]
    customer_and_channel: dict[str, Any]
    workflow: dict[str, Any]
    business_context_sources: list[dict[str, Any]]
    extracted_information: dict[str, Any]
    missing_information: list[str]
    ai_operational_summary: str
    policy_checks: dict[str, Any]
    deterministic_calculations: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    approval_decisions: list[dict[str, Any]]
    human_edits: list[dict[str, Any]]
    external_actions: list[dict[str, Any]]
    result: dict[str, Any]
    outcomes: list[dict[str, Any]]
    estimated_cost: Decimal = Decimal("0")
    latency_ms: int = 0
    retry_history: list[dict[str, Any]]
    errors_and_recovery: list[dict[str, Any]]
    steps: list[dict[str, Any]] = Field(default_factory=list)
