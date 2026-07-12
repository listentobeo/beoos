from decimal import Decimal
from typing import Any

import httpx

from app.core.config import Settings


class PaystackService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount: Decimal,
        currency: str,
        reference: str,
        callback_url: str,
        metadata: dict[str, Any],
    ) -> str:
        if not self._settings.paystack_secret_key:
            raise RuntimeError("Paystack secret key is not configured")
        amount_kobo = int((amount * Decimal("100")).quantize(Decimal("1")))
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.paystack.co/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {self._settings.paystack_secret_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": email,
                    "amount": amount_kobo,
                    "currency": currency,
                    "reference": reference,
                    "callback_url": callback_url,
                    "metadata": metadata,
                },
            )
        response.raise_for_status()
        payload = response.json()
        url = payload.get("data", {}).get("authorization_url")
        if not url:
            raise RuntimeError("Paystack returned no authorization URL")
        return str(url)
