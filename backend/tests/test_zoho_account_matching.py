from app.api.integrations import zoho_account_email_addresses


def test_reads_zoho_primary_mailbox_fields() -> None:
    assert zoho_account_email_addresses(
        {
            "primaryEmailAddress": "Admin@BeoArts.com",
            "mailboxAddress": "admin@beoarts.com",
            "incomingUserName": "admin@beoarts.com",
        }
    ) == {"admin@beoarts.com"}


def test_reads_confirmed_zoho_email_address_list() -> None:
    addresses = zoho_account_email_addresses(
        {
            "emailAddress": [
                {
                    "isAlias": False,
                    "isPrimary": True,
                    "mailId": "admin@beoarts.com",
                    "isConfirmed": True,
                }
            ]
        }
    )

    assert "admin@beoarts.com" in addresses


def test_reads_only_validated_send_mail_aliases() -> None:
    addresses = zoho_account_email_addresses(
        {
            "sendMailDetails": [
                {
                    "status": True,
                    "fromAddress": "admin@beoarts.com",
                    "userName": "benjamin@beoarts.com",
                },
                {
                    "status": False,
                    "fromAddress": "unverified@example.com",
                },
            ]
        }
    )

    assert "admin@beoarts.com" in addresses
    assert "benjamin@beoarts.com" in addresses
    assert "unverified@example.com" not in addresses
