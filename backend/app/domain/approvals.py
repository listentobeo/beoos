from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

CorrectionReason = Literal[
    "wrong_classification",
    "missing_information",
    "wrong_facts",
    "wrong_tone",
    "policy_violation",
    "unsafe_promise",
    "wrong_price",
    "unnecessary_escalation",
    "missed_escalation",
    "customer_context_misunderstood",
    "other",
]
ApprovalAction = Literal[
    "approve",
    "edit_and_approve",
    "reject",
    "request_more_information",
    "escalate",
    "cancel",
]


class ApprovalDecisionInput(BaseModel):
    action: ApprovalAction
    edited_payload: dict[str, Any] | None = None
    correction_reason: CorrectionReason | None = None
    decision_reason: str = Field(min_length=2, max_length=4_000)


class ApprovalView(BaseModel):
    id: UUID
    business_id: UUID
    business_name: str
    customer: dict[str, Any] | None
    workflow: dict[str, Any]
    proposed_action: dict[str, Any]
    ai_summary: str
    confidence: Decimal | None
    risk: str
    policy_checks: dict[str, Any]
    context_sources: list[dict[str, Any]]
    financial_impact: Decimal | None
    expires_at: datetime | None
    tool: dict[str, Any] | None
    required_role: str
    status: str
    original_payload: dict[str, Any]
    final_payload: dict[str, Any]
    execution_status: str | None
    execution_reference: str | None
    created_at: datetime
