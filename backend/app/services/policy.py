import re
from dataclasses import dataclass

from app.domain.email import EmailTriageResult, RecommendedAction


@dataclass(frozen=True)
class AutoSendDecision:
    allowed: bool
    reasons: list[str]


class EmailPolicyEngine:
    _currency_pattern = re.compile(r"(?:₦|NGN|naira|\$|€|£)\s*\d", re.IGNORECASE)
    _commitment_pattern = re.compile(
        r"\b(?:we guarantee|confirmed price|final price|refund approved|"
        r"discount approved|contract accepted)\b",
        re.IGNORECASE,
    )
    _blocked_risks = {"pricing", "payment", "refund", "complaint", "legal", "discount", "contract"}

    def __init__(
        self,
        *,
        signature: str = "Benjamin Odeke\nBeo Art Studio",
        whatsapp_number: str = "+2349075424681",
    ) -> None:
        self._signature = signature.replace("\r\n", "\n").strip()
        digits = "".join(character for character in whatsapp_number if character.isdigit())
        self._whatsapp_link = f"https://wa.me/{digits}"

    def evaluate(
        self,
        triage: EmailTriageResult,
        *,
        is_existing_client: bool,
        draft_body: str,
    ) -> AutoSendDecision:
        reasons: list[str] = []
        allowed_actions = {RecommendedAction.acknowledge, RecommendedAction.route_whatsapp}

        if triage.recommended_action not in allowed_actions:
            reasons.append("Only acknowledgements and deal-routing follow-ups can auto-send")
        if triage.confidence < 0.90:
            reasons.append("AI confidence is below the 0.90 acknowledgement threshold")
        if set(triage.risk_flags) & self._blocked_risks:
            reasons.append("The request involves pricing, money, a complaint, or a commitment")
        if self._currency_pattern.search(draft_body):
            reasons.append("The draft contains a price or currency amount")
        if self._commitment_pattern.search(draft_body):
            reasons.append("The draft contains an unauthorized commitment")
        normalized_body = draft_body.replace("\r\n", "\n").rstrip()
        if not normalized_body.endswith(self._signature):
            reasons.append("The draft is missing the approved Benjamin Odeke signature")
        if triage.category.value == "spam":
            reasons.append("Spam is never answered automatically")
        if is_existing_client and triage.recommended_action == RecommendedAction.route_whatsapp:
            reasons.append("Existing clients must remain on their current channel")
        if (
            triage.category.value == "art_school"
            and triage.recommended_action == RecommendedAction.route_whatsapp
        ):
            reasons.append("Art School enquiries remain in the email inbox")
        if triage.recommended_action == RecommendedAction.route_whatsapp and not triage.is_deal:
            reasons.append("Only genuine deal opportunities can be routed to WhatsApp")
        if (
            triage.recommended_action == RecommendedAction.route_whatsapp
            and self._whatsapp_link not in draft_body
        ):
            reasons.append("The WhatsApp handoff is missing the approved destination")
        if triage.is_professional and triage.recommended_action == RecommendedAction.route_whatsapp:
            reasons.append("Professional and corporate enquiries remain on email")

        return AutoSendDecision(allowed=not reasons, reasons=reasons)
