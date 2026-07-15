from app.api.forms import (
    _normalise_submission_data,
    _submitted_form_key,
)
from app.domain.forms import WebsiteLeadSubmission


def test_direct_html_form_fields_are_normalised() -> None:
    result = _normalise_submission_data(
        {
            "beoos_form_key": "tenant-secret",
            "full_name": "Ada Client",
            "_replyto": "ada@example.com",
            "whatsapp": "+234 800 000 0000",
            "project_type": "Mural",
            "price_range": "NGN 500,000",
            "timeline": "Next week",
            "details": "I need a mural for my office.",
            "page_url": "https://beoarts.com/contact",
        }
    )

    assert result == {
        "form_key": "tenant-secret",
        "name": "Ada Client",
        "email": "ada@example.com",
        "phone": "+234 800 000 0000",
        "service": "Mural",
        "budget": "NGN 500,000",
        "deadline": "Next week",
        "message": "I need a mural for my office.",
        "source_url": "https://beoarts.com/contact",
    }


def test_direct_form_can_build_message_from_custom_fields() -> None:
    result = _normalise_submission_data(
        {
            "form_key": "tenant-secret",
            "name": "Bulk Buyer",
            "email": "buyer@example.com",
            "canvas_size": "24x36 inches",
            "quantity": "12",
        },
        referer="https://example.com/order",
    )

    assert result["message"] == "Canvas Size: 24x36 inches\nQuantity: 12"
    assert result["source_url"] == "https://example.com/order"


def test_form_key_can_come_from_header_query_or_body() -> None:
    payload = WebsiteLeadSubmission(
        form_key="body-key",
        email="client@example.com",
        message="Hello",
    )

    assert (
        _submitted_form_key(
            payload,
            query_form_key=None,
            query_key=None,
            header_form_key="header-key",
        )
        == "header-key"
    )
    assert (
        _submitted_form_key(
            payload,
            query_form_key="query-form-key",
            query_key=None,
            header_form_key=None,
        )
        == "query-form-key"
    )
    assert (
        _submitted_form_key(
            payload,
            query_form_key=None,
            query_key="query-key",
            header_form_key=None,
        )
        == "query-key"
    )
    assert (
        _submitted_form_key(
            payload,
            query_form_key=None,
            query_key=None,
            header_form_key=None,
        )
        == "body-key"
    )
