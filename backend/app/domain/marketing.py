from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MarketingSource = Literal["search_console", "blogger", "clarity", "website", "manual"]


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
