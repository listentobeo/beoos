import hashlib
import hmac
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import HTTPException

from app.api.businesses import _select_phone_number
from app.api.whatsapp import _message_item, _verify_signature, _webhook_envelopes
from app.core.config import Settings
from app.infrastructure.models import (
    Direction,
    WhatsAppConnection,
    WhatsAppMessageSource,
    WhatsAppWebhookEvent,
)
from app.services.durable_jobs import (
    WHATSAPP_CONTACTS_SYNC_JOB,
    WHATSAPP_HISTORY_SYNC_JOB,
    WHATSAPP_WEBHOOK_JOB,
)
from app.services.whatsapp_coexistence import MetaCoexistenceService

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database" / "migrations" / "versions" / "20260727_0027_whatsapp_coexistence_v4.py"
)
FRONTEND = ROOT / "frontend" / "components" / "dashboard" / "whatsapp-settings-form.tsx"


def test_coexistence_migration_tracks_sync_and_webhook_processing() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for column in (
        "embedded_signup_version",
        "webhook_subscribed_at",
        "coexistence_verified_at",
        "sync_deadline_at",
        "contacts_sync_request_id",
        "history_sync_request_id",
        "history_sync_phase",
        "history_sync_progress",
        "payload_hash",
        "processing_error",
    ):
        assert column in migration
    assert "20260726_0026" in migration
    assert "def downgrade()" in migration
    assert "history_sync_progress" in WhatsAppConnection.__table__.c
    assert "payload_hash" in WhatsAppWebhookEvent.__table__.c


def test_frontend_surfaces_v4_coexistence_and_requires_finish_event() -> None:
    source = FRONTEND.read_text(encoding="utf-8")
    assert 'connectWithMeta("coexistence")' in source
    assert "FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING" in source
    assert "Embedded Signup v4" in source
    assert "Coexistence feature type is not used" not in source
    assert 'hostname.endsWith(".facebook.com")' in source
    assert "Complete synchronization within 24 hours" in source


def test_exact_phone_selection_refuses_ambiguous_waba() -> None:
    phones = [
        {"id": "one", "display_phone_number": "+234 800 000 0001"},
        {"id": "two", "display_phone_number": "+234 800 000 0002"},
    ]
    assert _select_phone_number(phones, "+2348000000002") == phones[1]
    assert _select_phone_number(phones, "") is None
    assert _select_phone_number([phones[0]], "") == phones[0]


def test_history_envelope_preserves_phase_chunk_and_progress() -> None:
    payload = {
        "entry": [
            {
                "id": "waba-1",
                "changes": [
                    {
                        "field": "history",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "history": [
                                {
                                    "metadata": {
                                        "phase": 2,
                                        "chunk_order": 4,
                                        "progress": 100,
                                    },
                                    "threads": [],
                                }
                            ],
                        },
                    }
                ],
            }
        ]
    }
    envelopes = _webhook_envelopes(payload)
    assert envelopes[0]["event_type"] == "history"
    assert envelopes[0]["waba_id"] == "waba-1"
    assert envelopes[0]["phone_number_id"] == "phone-1"
    assert envelopes[0]["phase"] == 2
    assert envelopes[0]["chunk_order"] == 4
    assert envelopes[0]["progress"] == 100


def test_business_app_echo_is_outbound_and_never_queues_ai() -> None:
    value = {
        "metadata": {
            "phone_number_id": "phone-1",
            "display_phone_number": "2348000000000",
        }
    }
    item = _message_item(
        value,
        {
            "id": "wamid.echo",
            "from": "2348000000000",
            "to": "2348111111111",
            "timestamp": "1738796547",
            "type": "text",
            "text": {"body": "Sent from the Business app"},
        },
        direction=Direction.outbound,
        customer_phone="2348111111111",
        enqueue_ai=False,
        is_history=False,
        message_source=WhatsAppMessageSource.business_app,
    )
    assert item is not None
    assert item.direction == Direction.outbound
    assert item.customer_phone == "2348111111111"
    assert item.enqueue_ai is False
    assert item.message_source == WhatsAppMessageSource.business_app


def test_production_whatsapp_webhook_signature_fails_closed() -> None:
    with pytest.raises(HTTPException) as missing_secret:
        _verify_signature(b"{}", None, Settings(app_env="production", meta_app_secret=""))
    assert missing_secret.value.status_code == 503

    body = b'{"entry":[]}'
    secret = "meta-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    _verify_signature(body, signature, Settings(app_env="production", meta_app_secret=secret))


@pytest.mark.asyncio
async def test_meta_coexistence_calls_subscribe_verify_and_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    responses = [
        {"success": True},
        {"is_on_biz_app": True, "platform_type": "CLOUD_API", "id": "phone-1"},
        {"messaging_product": "whatsapp", "request_id": "sync-contacts"},
        {"messaging_product": "whatsapp", "request_id": "sync-history"},
    ]

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def request(
            self,
            method: str,
            url: str,
            *,
            headers: dict[str, str],
            params: dict[str, str] | None,
            json: dict[str, str] | None,
        ) -> httpx.Response:
            assert headers["Authorization"] == "Bearer tenant-token"
            calls.append((method, url, json))
            return httpx.Response(
                200,
                json=responses.pop(0),
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(
        "app.services.whatsapp_coexistence.httpx.AsyncClient",
        lambda **_kwargs: FakeClient(),
    )
    service = MetaCoexistenceService(
        Settings(whatsapp_graph_base_url="https://graph.facebook.com/v25.0")
    )
    await service.subscribe_waba("tenant-token", "waba-1")
    verification = await service.verify_phone("tenant-token", "phone-1")
    contacts_id = await service.request_sync(
        "tenant-token",
        "phone-1",
        "smb_app_state_sync",
    )
    history_id = await service.request_sync("tenant-token", "phone-1", "history")

    assert verification.is_on_biz_app is True
    assert verification.platform_type == "CLOUD_API"
    assert contacts_id == "sync-contacts"
    assert history_id == "sync-history"
    assert calls[0][1].endswith("/waba-1/subscribed_apps")
    assert calls[2][2] == {
        "messaging_product": "whatsapp",
        "sync_type": "smb_app_state_sync",
    }
    assert calls[3][2] == {"messaging_product": "whatsapp", "sync_type": "history"}


def test_durable_job_types_cover_coexistence_and_fast_webhooks() -> None:
    assert WHATSAPP_CONTACTS_SYNC_JOB == "whatsapp.coexistence.contacts_sync"
    assert WHATSAPP_HISTORY_SYNC_JOB == "whatsapp.coexistence.history_sync"
    assert WHATSAPP_WEBHOOK_JOB == "whatsapp.webhook.process"
