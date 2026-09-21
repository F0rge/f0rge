"""WhatsApp click-to-chat send path."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient

from app.config import settings
from tests.test_comms_invoice_email import _create_invoice


async def test_whatsapp_click_invoice(owner_client: AsyncClient) -> None:
    invoice_id = await _create_invoice(owner_client, email="wa@ex.test")
    invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    customer_id = invoice.json()["customer_id"]
    patched = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "0824112001"},
    )
    assert patched.status_code == 200
    assert patched.json()["whatsapp_e164"] == "+27824112001"
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "click"
    assert body["provider"] == "whatsapp_click"
    assert body["status"] == "opened"
    parsed = urlparse(body["url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "wa.me"
    assert parsed.path == "/27824112001"
    assert "text" in parse_qs(parsed.query)
    listed = await owner_client.get(
        "/api/v1/comms/messages",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    assert listed.json()[0]["status"] == "opened"


async def test_whatsapp_landline_409(owner_client: AsyncClient) -> None:
    invoice_id = await _create_invoice(owner_client)
    invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    customer_id = invoice.json()["customer_id"]
    patched = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"phone": "0118802101"},
    )
    assert patched.status_code == 200
    assert patched.json()["whatsapp_e164"] is None
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "whatsapp"},
    )
    assert resp.status_code == 409


async def test_whatsapp_warehouse_403(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    invoice_id = await _create_invoice(owner_client)
    invoice = await owner_client.get(f"/api/v1/invoices/{invoice_id}")
    await owner_client.patch(
        f"/api/v1/customers/{invoice.json()['customer_id']}",
        json={"phone": "0824112001"},
    )
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
