import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.replicate_predictions import run_prediction


@pytest.mark.asyncio
async def test_throttled_creation_and_pending_prediction_are_paced() -> None:
    requests: list[httpx.Request] = []
    responses = [
        httpx.Response(429, headers={"Retry-After": "5"}),
        httpx.Response(201, json={"id": "test", "status": "starting"}),
        httpx.Response(200, json={"id": "test", "status": "succeeded", "output": "ok"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses.pop(0)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with patch(
            "app.services.replicate_predictions.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            result = await run_prediction(
                client,
                token="test",
                model="openai/gpt-5.4",
                inputs={"prompt": "test"},
                timeout_seconds=90,
            )
    assert result["output"] == "ok"
    assert [call.args[0] for call in sleep.call_args_list] == [5, 3]
    assert json.loads(requests[0].content) == {"input": {"prompt": "test"}}
    assert [request.method for request in requests] == ["POST", "POST", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [201, 422])
async def test_completed_prediction_needs_no_poll_and_invalid_input_is_not_retried(
    status: int,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"id": "test", "status": "succeeded", "output": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        if status == 422:
            with pytest.raises(httpx.HTTPStatusError):
                await run_prediction(
                    client, token="test", model="test/model", inputs={}, timeout_seconds=90
                )
        else:
            result = await run_prediction(
                client, token="test", model="test/model", inputs={}, timeout_seconds=90
            )
            assert result["id"] == "test"
    assert len(requests) == 1
