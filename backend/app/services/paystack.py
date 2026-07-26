import hashlib
import hmac
import json
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

    def verify_webhook_signature(self, body: bytes, signature: str | None) -> bool:
        if not self._settings.paystack_secret_key or not signature:
            return False
        expected = hmac.new(
            self._settings.paystack_secret_key.encode(),
            body,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def verify_transaction(self, reference: str) -> dict[str, Any]:
        if not self._settings.paystack_secret_key:
            raise RuntimeError("Paystack secret key is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {self._settings.paystack_secret_key}"},
            )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not payload.get("status") or not isinstance(data, dict):
            raise RuntimeError("Paystack verification returned invalid data")
        normalized = json.loads(json.dumps(data))
        return {str(key): value for key, value in normalized.items()}
