from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.infrastructure.models import FollowUpStatus

FollowUpCadence = Literal["standard", "hot", "gentle"]


class FollowUpScheduleRequest(BaseModel):
    cadence: FollowUpCadence = "standard"


class FollowUpTaskView(BaseModel):
    id: UUID
    business_id: UUID
    lead_id: UUID
    thread_id: UUID | None
    contact_id: UUID | None
    sequence_name: str
    step_number: int
    channel: str
    status: FollowUpStatus
    scheduled_for: datetime
    completed_at: datetime | None
    subject: str
    body_text: str
    error: str | None
    created_at: datetime
    updated_at: datetime


class FollowUpScheduleResponse(BaseModel):
    success: bool
    cancelled_existing: int
    tasks_created: int
    tasks: list[FollowUpTaskView]
