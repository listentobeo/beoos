"""Bounded prediction creation and polling shared by all AI activities."""

import asyncio
from typing import Any

import httpx


async def run_prediction(
    client: httpx.AsyncClient,
    *,
    token: str,
    model: str,
    inputs: dict[str, Any],
    timeout_seconds: int,
) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Prefer": "wait=10"}
    async with asyncio.timeout(timeout_seconds):
        # Only retry explicit throttling; uncertain POST outcomes must not duplicate paid runs.
        for attempt in range(3):
            response = await client.post(
                f"https://api.replicate.com/v1/models/{model}/predictions",
                headers=headers,
                json={"input": inputs},
            )
            if response.status_code != 429 or attempt == 2:
                response.raise_for_status()
                break
            try:
                delay = float(response.headers.get("Retry-After", str(2 ** (attempt + 1))))
            except ValueError:
                delay = float(2 ** (attempt + 1))
            await asyncio.sleep(max(1.0, min(delay, 30.0)))
        prediction = response.json()
        while True:
            status = prediction.get("status")
            if status == "succeeded":
                return prediction
            if status in {"failed", "canceled"}:
                raise RuntimeError(f"Replicate prediction {status}")
            await asyncio.sleep(3)
            response = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 429:
                continue
            response.raise_for_status()
            prediction = response.json()
