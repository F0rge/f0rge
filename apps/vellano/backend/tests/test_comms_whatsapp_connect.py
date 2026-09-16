"""WhatsApp Cloud API connect and webhook."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture(autouse=True)
def _comms_encryption_key() -> None:
    from tests.conftest import ensure_settings_encryption_key

    ensure_settings_encryption_key()


@pytest.fixture(autouse=True)
def _wa_verify_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "wa_verify_token", "verify-me")


async def test_patch_token_then_get_cloud_mode(owner_client: AsyncClient) -> None:
    patch = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "wa_phone_number_id": "123456789",
            "wa_business_account_id": "987654321",
            "wa_access_token": "secret-token",
            "wa_app_secret": "app-secret",
            "wa_invoice_template_name": "invoice_notice",
            "wa_template_lang": "en",
        },
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["has_wa_token"] is True
    assert body["has_wa_app_secret"] is True
    assert body["wa_configured"] is True
    assert body["whatsapp_mode"] == "cloud"
    assert body["wa_phone_number_id"] == "123456789"
    assert "wa_access_token" not in body
    assert "wa_access_token_encrypted" not in body
    assert "secret-token" not in str(body)

    fetched = await owner_client.get("/api/v1/settings/comms")
    assert fetched.status_code == 200
    assert fetched.json()["has_wa_token"] is True
    assert fetched.json()["whatsapp_mode"] == "cloud"
    assert "wa_access_token" not in fetched.json()


async def test_smtp_fields_still_work_alongside_whatsapp(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
            "wa_phone_number_id": "111",
            "wa_access_token": "tok",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["smtp_configured"] is True
    assert body["whatsapp_mode"] == "cloud"
    assert body["smtp_host"] == "smtp.example.com"


async def test_webhook_challenge(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "challenge-123",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge-123"


async def test_webhook_challenge_bad_token(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "nope",
            "hub.challenge": "challenge-123",
        },
    )
    assert resp.status_code == 403


async def test_webhook_bad_signature_403(
    owner_client: AsyncClient, async_client: AsyncClient
) -> None:
    saved = await owner_client.patch(
        "/api/v1/settings/comms",
        json={"wa_app_secret": "app-secret"},
    )
    assert saved.status_code == 200
    payload = json.dumps({"entry": []}).encode()
    resp = await async_client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 403


async def test_webhook_valid_signature_updates_outbox(
    owner_client: AsyncClient,
    async_client: AsyncClient,
) -> None:
    secret = "app-secret"
    saved = await owner_client.patch(
        "/api/v1/settings/comms",
        json={"wa_app_secret": secret},
    )
    assert saved.status_code == 200
    payload = json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {"id": "wamid.missing", "status": "delivered"},
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    resp = await async_client.post(
        "/api/v1/webhooks/whatsapp",
        content=payload,
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": f"sha256={digest}",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
