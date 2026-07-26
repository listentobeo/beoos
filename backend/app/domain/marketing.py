from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

MarketingSource = Literal["search_console", "blogger", "clarity", "website", "manual"]


class MarketingConnectionUpdate(BaseModel):
    website_url: str = Field(default="", max_length=500)
    search_console_property_url: str = Field(default="", max_length=500)
    blogger_blog_id: str = Field(default="", max_length=120)
    clarity_project_id: str = Field(default="", max_length=120)
    content_goals: str = Field(default="", max_length=3000)
    target_locations: str = Field(default="", max_length=1000)


class MarketingProviderStatus(BaseModel):
    key: str
    label: str
    configured: bool
    connected: bool
    setup_required: list[str] = Field(default_factory=list)
    notes: str = ""


class MarketingConnectionStatus(BaseModel):
    business_id: UUID
    settings: MarketingConnectionUpdate
    providers: list[MarketingProviderStatus]


class MarketingMetricImportRow(BaseModel):
    page_url: str = ""
    query: str = ""
    title: str = ""
    impressions: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    sessions: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    ctr: Decimal | None = None
    average_position: Decimal | None = None
    engagement_rate: Decimal | None = None
    avg_time_seconds: Decimal | None = None
    scroll_depth: Decimal | None = None
    metric_date: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)


class MarketingImportRequest(BaseModel):
    source: MarketingSource
    rows: list[MarketingMetricImportRow] = Field(min_length=1, max_length=500)


class MarketingImportResponse(BaseModel):
    success: bool
    source: str
    rows_received: int
    rows_created: int
    duplicates_skipped: int


class MarketingMetricView(BaseModel):
    id: UUID
    source: str
    page_url: str
    query: str
    title: str
    impressions: int
    clicks: int
    sessions: int
    leads: int
    ctr: Decimal | None
    average_position: Decimal | None
    engagement_rate: Decimal | None
    avg_time_seconds: Decimal | None
    scroll_depth: Decimal | None
    metric_date: datetime | None
    created_at: datetime


class MarketingTotal(BaseModel):
    source: str
    rows: int
    impressions: int
    clicks: int
    sessions: int
    leads: int


class MarketingPageOpportunity(BaseModel):
    page_url: str
    title: str
    impressions: int
    clicks: int
    sessions: int
    leads: int
    ctr: float
    average_position: float | None = None
    recommendation: str


class MarketingQueryOpportunity(BaseModel):
    query: str
    page_url: str
    impressions: int
    clicks: int
    ctr: float
    average_position: float | None = None
    recommendation: str


class MarketingContentCluster(BaseModel):
    topic: str
    impressions: int
    clicks: int
    queries: list[str]
    recommended_angle: str


class MarketingActionItem(BaseModel):
    priority: Literal["high", "medium", "low"]
    source: str
    label: str
    reason: str
    recommended_action: str
    page_url: str | None = None


class MarketingSummary(BaseModel):
    window_days: int
    totals: list[MarketingTotal]
    top_pages: list[MarketingPageOpportunity]
    query_opportunities: list[MarketingQueryOpportunity]
    content_clusters: list[MarketingContentCluster]
    action_items: list[MarketingActionItem]
    recent_metrics: list[MarketingMetricView]


class MarketingOpportunityCreate(BaseModel):
    source: str = Field(min_length=2, max_length=80)
    evidence: dict[str, Any]
    page_or_query: str = Field(min_length=1, max_length=2_000)
    baseline_metrics: dict[str, Any]
    recommendation: str = Field(min_length=5, max_length=10_000)
    expected_outcome: str = Field(min_length=3, max_length=2_000)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)


class MarketingOpportunityDecision(BaseModel):
    approve: bool
    reason: str = Field(min_length=2, max_length=2_000)


class MarketingExperimentCreate(BaseModel):
    opportunity_id: UUID
    approved_change: str = Field(min_length=5, max_length=10_000)
    target_page: str = Field(min_length=1, max_length=2_000)
    baseline_period_start: datetime
    baseline_period_end: datetime
    comparison_period_start: datetime
    comparison_period_end: datetime
    execution_method: Literal["manual", "approved_tool"] = "manual"
    approved_tool_call_id: UUID | None = None
    publish_automatically: bool = False

    @model_validator(mode="after")
    def prohibit_autonomous_publishing(self) -> "MarketingExperimentCreate":
        if self.publish_automatically:
            raise ValueError("Marketing publishing always requires explicit approval")
        if self.execution_method == "approved_tool" and self.approved_tool_call_id is None:
            raise ValueError("Approved-tool experiments require a completed tool call")
        if not (
            self.baseline_period_start
            < self.baseline_period_end
            <= self.comparison_period_start
            < self.comparison_period_end
        ):
            raise ValueError("Experiment periods must be ordered and non-overlapping")
        return self


class MarketingExperimentComplete(BaseModel):
    comparison_metrics: dict[str, Decimal | int | float]
    lesson: str = Field(min_length=3, max_length=10_000)
