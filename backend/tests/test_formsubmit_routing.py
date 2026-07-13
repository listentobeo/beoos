from app.services.email_sync import _extract_formsubmit_contact


def test_formsubmit_contact_is_extracted_from_body() -> None:
    result = _extract_formsubmit_contact(
        body_text="\n".join(
            [
                "Name: Ada Client",
                "Email: ada@example.com",
                "Phone: +234 800 000 0000",
                "Message: I need a mural quote.",
            ]
        ),
        body_html="",
        sender_email="submissions@formsubmit.co",
        summary={"subject": "New Contact Request"},
    )

    assert result == {
        "email": "ada@example.com",
        "name": "Ada Client",
        "phone": "+234 800 000 0000",
    }


def test_non_formsubmit_sender_is_not_overridden() -> None:
    result = _extract_formsubmit_contact(
        body_text="Email: client@example.com",
        body_html="",
        sender_email="real.sender@example.com",
        summary={"subject": "Hello"},
    )

    assert result is None
