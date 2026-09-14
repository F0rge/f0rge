"""Email credit notes and laybys; layby PDF."""

from __future__ import annotations

from typing import Optional

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from pypdf import PdfReader
from io import BytesIO

from app.config import settings
from tests.test_comms_smtp import _FakeSMTP
from tests.test_laybys import _create_till_user, _layby_payload, _stocked_sku_at_bedford
from tests.test_purchase_orders import _relogin_owner


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


async def _configure_smtp(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/settings/comms",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_from_address": "shop@example.com",
            "smtp_username": "shop@example.com",
            "smtp_password": "pw",
        },
    )
    assert resp.status_code == 200


async def _create_credit_note(
    owner_client: AsyncClient, email: Optional[str] = "cn@ex.test"
) -> str:
    payload = {"name": "CN Mail Customer"}
    if email is not None:
        payload["email"] = email
    customer = await owner_client.post("/api/v1/contacts", json=payload)
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Sofa", "qty": 1, "unit_ex_vat": "2000.00"}],
        },
    )
    assert invoice.status_code == 201
    credit = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice.json()["id"], "reason": "Returned"},
    )
    assert credit.status_code == 201
    return credit.json()["id"]


async def test_credit_note_send_email(
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    credit_id = await _create_credit_note(owner_client)
    resp = await owner_client.post(
        f"/api/v1/credit-notes/{credit_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert list(fake_smtp.instances[0].messages[0].iter_attachments())


async def test_credit_note_warehouse_403(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    credit_id = await _create_credit_note(owner_client)
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse@example.com", "password": settings.seed_warehouse_password},
    )
    assert login.status_code == 200
    resp = await async_client.post(
        f"/api/v1/credit-notes/{credit_id}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 403


async def test_layby_pdf_and_send(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "LB-MAIL")
    customer = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Layby Mail Customer", "email": "layby@ex.test"},
    )
    assert customer.status_code == 201
    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer.json()["id"], bedford_id, sku_id, hold_stock=False),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]
    pdf = await owner_client.get(f"/api/v1/laybys/{layby_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert created.json()["layby_number"] in text
    sent = await till.post(f"/api/v1/laybys/{layby_id}/send", json={"channel": "email"})
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert list(fake_smtp.instances[0].messages[0].iter_attachments())


async def test_cancelled_layby_send_409(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    fake_smtp: type[_FakeSMTP],
) -> None:
    await _configure_smtp(owner_client)
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "LB-CAN")
    customer = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Layby Cancel Customer", "email": "cancel@ex.test"},
    )
    assert customer.status_code == 201
    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer.json()["id"], bedford_id, sku_id, hold_stock=False),
    )
    assert created.status_code == 201
    layby_id = created.json()["id"]
    cancelled = await till.post(f"/api/v1/laybys/{layby_id}/cancel")
    assert cancelled.status_code == 200
    sent = await till.post(f"/api/v1/laybys/{layby_id}/send", json={"channel": "email"})
    assert sent.status_code == 409
    assert fake_smtp.instances == []


async def test_layby_warehouse_send_403(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _configure_smtp(owner_client)
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "LB-WH")
    await _relogin_owner(owner_client)
    customer = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Layby WH Customer", "email": "wh@ex.test"},
    )
    assert customer.status_code == 201
    till = await _create_till_user(async_client, owner_client)
    created = await till.post(
        "/api/v1/laybys",
        json=_layby_payload(customer.json()["id"], bedford_id, sku_id, hold_stock=False),
    )
    assert created.status_code == 201
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse@example.com", "password": settings.seed_warehouse_password},
    )
    assert login.status_code == 200
    resp = await async_client.post(
        f"/api/v1/laybys/{created.json()['id']}/send",
        json={"channel": "email"},
    )
    assert resp.status_code == 403
