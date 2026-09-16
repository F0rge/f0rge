"""WhatsApp Cloud API send (Graph mocked)."""

from __future__ import annotations

import json
from typing import Any, Optional

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.test_comms_invoice_email import _create_invoice


class _FakeResponse:
    def __init__(self, status_code: int, data: dict) -> None:
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)
        self.content = self.text.encode()

    def json(self) -> dict:
        return self._data


class _FakeAsyncClient:
    calls: list[tuple[str, dict[str, Any]]] = []
    fail_template = False

    def __init__(self, timeout: Optional[float] = None) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        _FakeAsyncClient.calls.append((url, kwargs))
        payload = kwargs.get("json") or {}
        if _FakeAsyncClient.fail_template and payload.get("type") == "template":
            return _FakeResponse(
                400,
                {
                    "error": {
                        "message": ("Message failed to send because more than 24 hours have passed")
                    }
                },
            )
        if url.endswith("/media"):
            return _FakeResponse(200, {"id": "media-1"})
        if payload.get("type") == "document":
            return _FakeResponse(200, {"messages": [{"id": "wamid.doc"}]})
        return _FakeResponse(200, {"messages": [{"id": "wamid.tpl"}]})


@pytest.fixture(autouse=True)
def _comms_encryption_key() -> None:
    from tests.conftest import ensure_settings_encryption_key

    ensure_settings_encryption_key()


@pytest.fixture
def fake_graph(monkeypatch: pytest.MonkeyPatch) -> type[_FakeAsyncClient]:
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.fail_template = False
    monkeypatch.setattr("app.services.comms.whatsapp.httpx.AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


async def _connect_cloud(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "wa_phone_number_id": "123456789",
            "wa_access_token": "secret-token",
            "wa_invoice_template_name": "invoice_notice",
            "wa_template_lang": "en",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["whatsapp_mode"] == "cloud"


async def _mobile_invoice(owner_client: AsyncClient) -> str:
    invoice_id = await _create_invoice(owner_client, email="wa-cloud@ex.test")
    invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    customer_id = invoice.json()["customer_id"]
    patched = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "0824112001"},
    )
    assert patched.status_code == 200
    return invoice_id


async def test_cloud_send_invoice(
    owner_client: AsyncClient,
    fake_graph: type[_FakeAsyncClient],
) -> None:
    await _connect_cloud(owner_client)
    invoice_id = await _mobile_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "cloud"
    assert body["provider"] == "whatsapp_cloud"
    assert body["status"] == "sent"
    assert body.get("url") in {None, ""}
    assert len(fake_graph.calls) == 3
    assert fake_graph.calls[0][0].endswith("/messages")
    assert fake_graph.calls[1][0].endswith("/media")
    assert fake_graph.calls[2][0].endswith("/messages")
    auth = fake_graph.calls[0][1]["headers"]["Authorization"]
    assert auth.startswith("Bearer ")
    listed = await owner_client.get(
        "/api/v1/comms/messages",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    row = listed.json()[0]
    assert row["provider"] == "whatsapp_cloud"
    assert row["status"] == "sent"
    assert row["provider_message_id"] == "wamid.doc"


async def test_cloud_off_still_click(owner_client: AsyncClient) -> None:
    invoice_id = await _mobile_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "click"
    assert resp.json()["provider"] == "whatsapp_click"


async def test_cloud_no_e164_409(
    owner_client: AsyncClient,
    fake_graph: type[_FakeAsyncClient],
) -> None:
    await _connect_cloud(owner_client)
    invoice_id = await _create_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 409
    assert fake_graph.calls == []


async def test_cloud_warehouse_403(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    fake_graph: type[_FakeAsyncClient],
) -> None:
    await _connect_cloud(owner_client)
    invoice_id = await _mobile_invoice(owner_client)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse@example.com", "password": settings.seed_warehouse_password},
    )
    assert login.status_code == 200
    resp = await async_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 403
    assert fake_graph.calls == []


async def test_cloud_template_window_409(
    owner_client: AsyncClient,
    fake_graph: type[_FakeAsyncClient],
) -> None:
    fake_graph.fail_template = True
    await _connect_cloud(owner_client)
    invoice_id = await _mobile_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 409
    assert "24 hours" in resp.json()["detail"]
    listed = await owner_client.get(
        "/api/v1/comms/messages",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    assert listed.json()[0]["status"] == "failed"
