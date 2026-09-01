"""S6 credit note tests."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader


async def _create_invoice(owner_client: AsyncClient) -> dict:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "CN Customer"},
    )
    assert customer_resp.status_code == 201
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Sofa", "qty": 1, "unit_ex_vat": "2000.00"}],
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def test_credit_note_reverses_invoice(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client)
    resp = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice["id"], "reason": "Returned"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["credit_note_number"] == "CN-0001"
    assert body["total_inc_vat"] == invoice["total_inc_vat"]

    accounts = (await owner_client.get("/api/v1/accounts")).json()
    balances = {a["code"]: a["balance_zar"] for a in accounts}
    assert balances["1200"] == "0.00"
    assert balances["4000"] == "0.00"
    assert balances["2200"] == "0.00"


async def test_duplicate_credit_note_conflict(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client)
    first = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice["id"]},
    )
    assert first.status_code == 201

    second = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice["id"]},
    )
    assert second.status_code == 409


async def test_till_cannot_create_credit_note(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    invoice = await _create_invoice(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-cn@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-cn@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice["id"]},
    )
    assert resp.status_code == 403


async def test_credit_note_pdf(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client)
    created = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice["id"], "reason": "Returned"},
    )
    assert created.status_code == 201
    body = created.json()

    pdf_resp = await owner_client.get(f"/api/v1/credit-notes/{body['id']}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    text = _pdf_text(pdf_resp.content)
    assert "Credit Note" in text
    assert "CN-0001" in text
    assert invoice["invoice_number"] in text
    assert "Returned" in text


async def test_unauthenticated_credit_note_pdf_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/credit-notes/00000000-0000-0000-0000-000000000001/pdf"
    )
    assert resp.status_code == 401
