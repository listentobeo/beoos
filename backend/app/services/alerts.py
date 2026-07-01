import asyncio

import resend

from app.core.config import Settings


class AlertService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        resend.api_key = settings.resend_api_key

    async def send_urgent_email(
        self,
        *,
        recipient: str,
        thread_subject: str,
        sender_email: str,
    ) -> None:
        if not self._settings.resend_api_key:
            return

        def send() -> None:
            resend.Emails.send(
                {
                    "from": self._settings.alert_from_email,
                    "to": [recipient],
                    "subject": f"[BeoOS Urgent] {thread_subject}",
                    "text": (
                        f"BeoOS flagged an urgent email from {sender_email}.\n\n"
                        "Open the Urgent section in BeoOS to review it."
                    ),
                    "headers": {"X-BeoOS-System": "urgent-alert"},
                }
            )

        await asyncio.to_thread(send)
