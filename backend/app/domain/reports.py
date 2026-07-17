from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


class DailyReportSettings(BaseModel):
    enabled: bool = False
    time: str = Field(default="18:00", pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(default="Africa/Lagos", min_length=2, max_length=64)
    email: EmailStr | None = None
    push_enabled: bool = True
    last_sent_on: str | None = None
    last_sent_at: datetime | None = None


class DailyReportSettingsUpdate(BaseModel):
    enabled: bool
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezone: str = Field(min_length=2, max_length=64)
    email: EmailStr | None = None
    push_enabled: bool = True


class DailyReportTotals(BaseModel):
    inbound_messages: int
    unread_messages: int
    whatsapp_messages: int
    needs_approval: int
    leads_created: int
    hot_leads: int
    quotes_created: int
    quotes_accepted: int
    followups_due: int
    pending_drafts: int
    open_quote_value: Decimal
    accepted_quote_value: Decimal


class DailyReportActivityItem(BaseModel):
    label: str
    detail: str
    occurred_at: datetime
    href: str | None = None


class DailyReportPreview(BaseModel):
    business_id: str
    business_name: str
    report_date: str
    timezone: str
    recipient: str
    subject: str
    totals: DailyReportTotals
    highlights: list[str]
    action_items: list[str]
    recent_activity: list[DailyReportActivityItem]


class DailyReportSendResult(BaseModel):
    success: bool
    email_sent: bool
    push_sent: int
    recipient: str
    subject: str
    message: str
    preview: DailyReportPreview


def normalized_daily_report_settings(
    settings: dict | None,
    *,
    fallback_email: str,
    fallback_timezone: str,
) -> DailyReportSettings:
    raw_settings = (settings or {}).get("daily_report", {})
    if not isinstance(raw_settings, dict):
        raw_settings = {}
    merged = {
        "email": fallback_email,
        "timezone": fallback_timezone,
        **raw_settings,
    }
    if not merged.get("email"):
        merged["email"] = fallback_email
    if not merged.get("timezone"):
        merged["timezone"] = fallback_timezone
    return DailyReportSettings.model_validate(merged)
