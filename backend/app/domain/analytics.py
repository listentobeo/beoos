from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AnalyticsBucket(BaseModel):
    key: str
    label: str
    count: int
    value: Decimal | None = None


class AnalyticsTotals(BaseModel):
    conversations: int
    inbound_messages: int
    outbound_messages: int
    unread_messages: int
    needs_approval: int
    leads: int
    quotes: int
    pending_drafts: int
    due_followups: int


class AnalyticsConversion(BaseModel):
    leads_created: int
    quotes_created: int
    quotes_accepted: int
    lead_to_quote_rate: float
    quote_acceptance_rate: float
    open_quote_value: Decimal
    accepted_quote_value: Decimal


class AnalyticsRecentActivity(BaseModel):
    label: str
    detail: str
    occurred_at: datetime
    href: str | None = None


class AnalyticsSummary(BaseModel):
    window_days: int
    totals: AnalyticsTotals
    conversion: AnalyticsConversion
    inbox_by_provider: list[AnalyticsBucket]
    thread_statuses: list[AnalyticsBucket]
    lead_sources: list[AnalyticsBucket]
    lead_stages: list[AnalyticsBucket]
    lead_temperatures: list[AnalyticsBucket]
    quote_statuses: list[AnalyticsBucket]
    follow_up_statuses: list[AnalyticsBucket]
    recent_activity: list[AnalyticsRecentActivity]
