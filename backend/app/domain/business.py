import secrets
from typing import Any

from pydantic import BaseModel, Field


class BusinessAIPolicy(BaseModel):
    auto_acknowledge: bool = True
    auto_route_whatsapp: bool = True
    confidence_threshold: float = Field(default=0.9, ge=0.5, le=1.0)
    require_approval_for_prices: bool = True
    require_approval_for_commitments: bool = True
    require_approval_for_risk_flags: bool = True
    existing_clients_stay_on_current_channel: bool = True
    art_school_stays_in_email: bool = True
    professionals_stay_in_email: bool = True
    route_only_deals_to_whatsapp: bool = True
    custom_instructions: str = Field(
        default=(
            "Service pages are authoritative. Blog prices are educational estimates. "
            "Route only genuine new deal opportunities to WhatsApp."
        ),
        max_length=2000,
    )


def default_ai_policy() -> dict[str, Any]:
    return BusinessAIPolicy().model_dump()


def normalized_ai_policy(settings: dict[str, Any] | None) -> BusinessAIPolicy:
    raw_policy = (settings or {}).get("ai_policy", {})
    if not isinstance(raw_policy, dict):
        raw_policy = {}
    return BusinessAIPolicy.model_validate(raw_policy)


def default_business_settings() -> dict[str, Any]:
    return {
        "history_days": 365,
        "price_authority": "service_pages",
        "blog_prices_are_estimates": True,
        "website_form_key": secrets.token_urlsafe(24),
        "ai_policy": default_ai_policy(),
    }


def website_form_key(settings: dict[str, Any] | None) -> str:
    value = (settings or {}).get("website_form_key")
    return str(value) if value else ""


def ensure_website_form_key(settings: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    merged = dict(settings or {})
    if website_form_key(merged):
        return merged, False
    merged["website_form_key"] = secrets.token_urlsafe(24)
    return merged, True
