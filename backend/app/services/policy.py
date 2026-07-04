import re
from dataclasses import dataclass

from app.domain.business import BusinessAIPolicy
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
        policy: BusinessAIPolicy | None = None,
    ) -> None:
        self._signature = signature.replace("\r\n", "\n").strip()
        self._policy = policy or BusinessAIPolicy()
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
        allowed_actions: set[RecommendedAction] = set()
        if self._policy.auto_acknowledge:
            allowed_actions.add(RecommendedAction.acknowledge)
        if self._policy.auto_route_whatsapp:
            allowed_actions.add(RecommendedAction.route_whatsapp)

        if triage.recommended_action not in allowed_actions:
            reasons.append("This business policy does not allow this action to auto-send")
        if triage.confidence < self._policy.confidence_threshold:
            reasons.append(
                "AI confidence is below this business threshold "
                f"({self._policy.confidence_threshold:.2f})"
            )
        if (
            self._policy.require_approval_for_risk_flags
            and set(triage.risk_flags) & self._blocked_risks
        ):
            reasons.append("The request involves pricing, money, a complaint, or a commitment")
        if self._policy.require_approval_for_prices and self._currency_pattern.search(draft_body):
            reasons.append("The draft contains a price or currency amount")
        if (
            self._policy.require_approval_for_commitments
            and self._commitment_pattern.search(draft_body)
        ):
            reasons.append("The draft contains an unauthorized commitment")
        normalized_body = draft_body.replace("\r\n", "\n").rstrip()
        if not normalized_body.endswith(self._signature):
            reasons.append("The draft is missing the approved business signature")
        if triage.category.value == "spam":
            reasons.append("Spam is never answered automatically")
        if (
            self._policy.existing_clients_stay_on_current_channel
            and is_existing_client
            and triage.recommended_action == RecommendedAction.route_whatsapp
        ):
            reasons.append("Existing clients must remain on their current channel")
        if (
            self._policy.art_school_stays_in_email
            and triage.category.value == "art_school"
            and triage.recommended_action == RecommendedAction.route_whatsapp
        ):
            reasons.append("Art School enquiries remain in the email inbox")
        if (
            self._policy.route_only_deals_to_whatsapp
            and triage.recommended_action == RecommendedAction.route_whatsapp
            and not triage.is_deal
        ):
            reasons.append("Only genuine deal opportunities can be routed to WhatsApp")
        if (
            triage.recommended_action == RecommendedAction.route_whatsapp
            and self._whatsapp_link not in draft_body
        ):
            reasons.append("The WhatsApp handoff is missing the approved destination")
        if (
            self._policy.professionals_stay_in_email
            and triage.is_professional
            and triage.recommended_action == RecommendedAction.route_whatsapp
        ):
            reasons.append("Professional and corporate enquiries remain on email")

        return AutoSendDecision(allowed=not reasons, reasons=reasons)
