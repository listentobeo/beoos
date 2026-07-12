from dataclasses import dataclass
from datetime import UTC, datetime

from app.infrastructure.models import EmailAnalysis, EmailThread, LeadStage, LeadTemperature


@dataclass(frozen=True)
class LeadQualification:
    score: int
    temperature: LeadTemperature
    stage: LeadStage
    summary: str
    reasons: list[str]
    qualified_at: datetime


def qualify_lead(
    *,
    thread: EmailThread | None,
    analysis: EmailAnalysis | None,
    requested_stage: LeadStage,
) -> LeadQualification:
    score = 20
    reasons: list[str] = []
    extracted = analysis.extracted_fields if analysis else {}

    if thread and thread.is_deal:
        score += 25
        reasons.append("AI detected a deal opportunity")
    if analysis and analysis.is_deal:
        score += 20
        reasons.append("Latest AI analysis confirms buying intent")
    if _field(extracted, "service"):
        score += 10
        reasons.append("Service is known")
    if _field(extracted, "budget"):
        score += 15
        reasons.append("Budget was mentioned")
    if _field(extracted, "deadline"):
        score += 15
        reasons.append("Deadline or urgency was mentioned")
    if _field(extracted, "phone"):
        score += 5
        reasons.append("Phone number is available")
    if analysis and analysis.urgency:
        score += 10
        reasons.append("Request appears urgent")
    if analysis and "pricing" in analysis.risk_flags:
        score += 5
        reasons.append("Client asked about pricing")

    score = min(score, 100)
    if score >= 75:
        temperature = LeadTemperature.hot
        stage = LeadStage.qualified
        summary = "Hot lead: ready for direct follow-up and quote preparation."
    elif score >= 45:
        temperature = LeadTemperature.warm
        stage = LeadStage.contacted if requested_stage == LeadStage.new else requested_stage
        summary = "Warm lead: enough interest to follow up and qualify further."
    else:
        temperature = LeadTemperature.cold
        stage = requested_stage
        summary = "Cold lead: needs more information before quoting."

    return LeadQualification(
        score=score,
        temperature=temperature,
        stage=stage,
        summary=summary,
        reasons=reasons or ["Not enough buying signals yet"],
        qualified_at=datetime.now(UTC),
    )


def _field(values: dict[str, object], key: str) -> str | None:
    value = values.get(key)
    return str(value).strip() if value else None
