from app.domain.beo_enquiry import (
    BeoCommissionEnquiryInput,
    BeoCommissionEnquiryOutput,
    CustomerIdentity,
    EnquiryOutcomeCreate,
)
from app.services.beo_enquiry_workflow import (
    WORKFLOW_KEY,
    _approval_reasons,
    _missing_fields,
)


def _enquiry(**overrides: object) -> BeoCommissionEnquiryInput:
    values: dict[str, object] = {
        "customer": CustomerIdentity(email="client@example.com"),
        "channel": "website_form",
        "message": "I need a portrait quote",
        "requested_service": "portrait",
        "medium": "oil",
        "dimensions": "60x90cm",
        "deadline": "2026-10-01",
        "location": "Lagos",
    }
    values.update(overrides)
    return BeoCommissionEnquiryInput.model_validate(values)


def test_reference_workflow_key_and_contract_are_stable() -> None:
    assert WORKFLOW_KEY == "beo_art_commission_enquiry_v1"
    assert set(BeoCommissionEnquiryInput.model_fields).issuperset(
        {
            "customer",
            "channel",
            "message",
            "attachments",
            "requested_service",
            "medium",
            "dimensions",
            "number_of_subjects",
            "reference_image_available",
            "deadline",
            "location",
            "framing",
            "delivery",
            "budget",
            "occasion",
            "urgency",
            "sentiment",
            "missing_information",
        }
    )
    assert set(BeoCommissionEnquiryOutput.model_fields).issuperset(
        {
            "structured_analysis",
            "qualification_recommendation",
            "missing_questions",
            "suggested_reply",
            "proposed_crm_update",
            "proposed_follow_up",
            "policy_result",
            "approval_required",
            "operational_trace",
        }
    )


def test_missing_information_is_deterministic() -> None:
    assert _missing_fields(_enquiry()) == []
    assert _missing_fields(_enquiry(dimensions=None, deadline=None)) == [
        "dimensions",
        "deadline",
    ]


def test_mandatory_human_approval_rules_cover_high_risk_cases() -> None:
    enquiry = _enquiry(
        urgency=True,
        sentiment="angry",
        location="International",
        medium="unobtainium",
        reference_image_available=False,
        message=(
            "I am furious. Rush this international delivery, guarantee it, apply a discount, "
            "and quote me without a reference."
        ),
    )
    reasons = _approval_reasons(
        enquiry,
        {"risk_flags": ["discount", "legal", "refund"]},
        [],
    )
    for expected in (
        "discount request",
        "refund request",
        "legal or privacy concern",
        "rush commitment",
        "angry customer",
        "international delivery",
        "uncertain reference quality",
        "unusual materials",
        "custom pricing",
        "promise outside policy",
    ):
        assert expected in reasons


def test_outcome_contract_covers_business_funnel_and_quality() -> None:
    for outcome_type in (
        "customer_replied",
        "complete_information_received",
        "lead_qualified",
        "quote_created",
        "quote_sent",
        "quote_accepted",
        "deposit_paid",
        "order_won",
        "order_lost",
        "loss_reason",
        "response_time",
        "correction_rate",
    ):
        outcome = EnquiryOutcomeCreate(
            outcome_type=outcome_type,
            status="observed",
            source="test",
        )
        assert outcome.outcome_type == outcome_type
