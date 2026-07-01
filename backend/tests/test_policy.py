from app.domain.email import EmailTriageResult, ExtractedClientFields, RecommendedAction
from app.infrastructure.models import ThreadCategory
from app.services.policy import EmailPolicyEngine

SAFE_BODY = (
    "Thank you for your portrait enquiry. Continue with us on "
    "https://wa.me/2349075424681.\n\nBenjamin Odeke\nBeo Art Studio"
)


def triage(**overrides: object) -> EmailTriageResult:
    values: dict[str, object] = {
        "category": ThreadCategory.portrait,
        "intent": "Commission a portrait",
        "confidence": 0.97,
        "urgency": False,
        "is_deal": True,
        "is_professional": False,
        "risk_flags": [],
        "extracted_fields": ExtractedClientFields(service="portrait"),
        "recommended_action": RecommendedAction.route_whatsapp,
        "acknowledgement_subject": "Re: Your portrait enquiry",
        "acknowledgement_body": SAFE_BODY,
    }
    values.update(overrides)
    return EmailTriageResult.model_validate(values)


def test_allows_safe_high_confidence_deal_handoff() -> None:
    decision = EmailPolicyEngine().evaluate(
        triage(), is_existing_client=False, draft_body=SAFE_BODY
    )
    assert decision.allowed is True


def test_blocks_prices_even_when_confidence_is_high() -> None:
    decision = EmailPolicyEngine().evaluate(
        triage(),
        is_existing_client=False,
        draft_body=f"The portrait costs ₦85,000.\n\n{SAFE_BODY}",
    )
    assert decision.allowed is False
    assert any("currency" in reason for reason in decision.reasons)


def test_existing_client_cannot_be_pushed_to_whatsapp() -> None:
    decision = EmailPolicyEngine().evaluate(triage(), is_existing_client=True, draft_body=SAFE_BODY)
    assert decision.allowed is False
    assert any("current channel" in reason for reason in decision.reasons)


def test_art_school_stays_in_email() -> None:
    result = triage(category=ThreadCategory.art_school)
    decision = EmailPolicyEngine().evaluate(result, is_existing_client=False, draft_body=SAFE_BODY)
    assert decision.allowed is False
    assert any("Art School" in reason for reason in decision.reasons)


def test_low_confidence_requires_approval() -> None:
    decision = EmailPolicyEngine().evaluate(
        triage(confidence=0.72), is_existing_client=False, draft_body=SAFE_BODY
    )
    assert decision.allowed is False
    assert any("confidence" in reason for reason in decision.reasons)
