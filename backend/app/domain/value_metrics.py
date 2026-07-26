from decimal import Decimal

from pydantic import BaseModel, Field


class WorkflowBaselineUpsert(BaseModel):
    workflow_key: str = Field(min_length=2, max_length=160)
    prior_response_time_minutes: Decimal | None = Field(default=None, ge=0)
    manual_handling_time_minutes: Decimal | None = Field(default=None, ge=0)
    prior_conversion_rate: Decimal | None = Field(default=None, ge=0, le=1)
    missed_lead_frequency_monthly: Decimal | None = Field(default=None, ge=0)
    common_mistake_cost: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", min_length=3, max_length=3)
