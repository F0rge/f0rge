"""Email a tax invoice PDF via SMTP."""

from __future__ import annotations

from typing import Optional

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.config import settings
from tests.test_comms_smtp import _FakeSMTP


@pytest.fixture(autouse=True)
def _comms_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    _FakeSMTP.fail_login = False
    monkeypatch.setattr("smtplib.SMTP", _FakeSMTP)
    monkeypatch.setattr("smtplib.SMTP_SSL", _FakeSMTP)
    return _FakeSMTP


@pytest.fixture(autouse=True)
def _comms_encryption_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "settings_encryption_key", Fernet.generate_key().decode())


async def _login(client: AsyncClient, email: str, password: str) -> AsyncClient:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return client


async def _configure_smtp(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_username": "shop@example.com",
            "smtp_password": "pw",
            "smtp_from_address": "shop@example.com",
            "smtp_from_name": "Vellano",
        },
    )
    assert resp.status_code == 200


async def _create_invoice(
    owner_client: AsyncClient,
    *,
    email: Optional[str] = "buyer@customer.test",
) -> str:
    payload = {"name": "Invoice Mail Customer"}
    if email is not None:
        payload["email"] = email
    customer = await owner_client.post("/api/v1/contacts", json=payload)
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Dining table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert invoice.status_code == 201
    return invoice.json()["id"]


async def test_owner_sends_invoice_email(
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    invoice_id = await _create_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["provider"] == "smtp"
    assert len(fake_smtp.instances) == 1
    msg = fake_smtp.instances[0].messages[0]
    attachments = list(msg.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == "application/pdf"
    listed = await owner_client.get(
        "/api/v1/comms/messages",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "sent"


async def test_till_and_books_can_send(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    invoice_id = await _create_invoice(owner_client)
    await _login(async_client, "till@example.com", settings.seed_till_password)
    till_send = await async_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert till_send.status_code == 200
    await _login(async_client, "books@example.com", settings.seed_books_password)
    books_send = await async_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert books_send.status_code == 200


async def test_warehouse_send_forbidden(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    invoice_id = await _create_invoice(owner_client)
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    resp = await async_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 403


async def test_buyer_send_forbidden(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    invoice_id = await _create_invoice(owner_client)
    await _login(async_client, "buyer@example.com", settings.seed_buyer_password)
    resp = await async_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 403


async def test_unauthenticated_send_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/invoices/00000000-0000-0000-0000-000000000001/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 401


async def test_missing_email_409_no_smtp(
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    invoice_id = await _create_invoice(owner_client, email=None)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 409
    assert "email" in resp.json()["detail"].lower()
    assert fake_smtp.instances == []


async def test_unconfigured_smtp_503(
    owner_client: AsyncClient,
) -> None:
    invoice_id = await _create_invoice(owner_client)
    resp = await owner_client.post(
        f"/api/v1/invoices/{invoice_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "comms_smtp_unconfigured"
