"""S6 tax invoice tests."""

from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader


async def _create_customer(owner_client: AsyncClient) -> str:
    resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Invoice Customer"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def test_unauthenticated_create_invoice_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "issue_date": "2026-09-01",
            "lines": [{"description": "Table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 401


async def test_create_invoice_posts_journal_and_pdf(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(owner_client)
    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Dining table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["invoice_number"] == "INV-0001"
    assert body["subtotal_ex_vat"] == "1000.00"
    assert body["vat_amount"] == "150.00"
    assert body["total_inc_vat"] == "1150.00"
    assert body["balance"] == "1150.00"

    accounts = (await owner_client.get("/api/v1/accounts")).json()
    balances = {a["code"]: a["balance_zar"] for a in accounts}
    assert balances["1200"] == "1150.00"
    assert balances["4000"] == "-1000.00"
    assert balances["2200"] == "-150.00"

    pdf_resp = await owner_client.get(f"/api/v1/invoices/{body['id']}/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    text = _pdf_text(pdf_resp.content)
    assert "INV-0001" in text
    assert "150.00" in text
    assert "1150.00" in text
    assert "Tax Invoice" in text


async def test_books_can_create_invoice(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_customer(owner_client)
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-invoice@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-invoice@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Chair", "qty": 2, "unit_ex_vat": "500.00"}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["invoice_number"] == "INV-0001"
