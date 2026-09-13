"""Books period lock independent of VAT201."""

from __future__ import annotations

from httpx import AsyncClient
from tests.test_vat201_periods import _create_period as _create_vat201_period


async def _create_named_customer(owner_client: AsyncClient, name: str) -> str:
    resp = await owner_client.post("/api/v1/contacts", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_books_period(owner_client: AsyncClient, period_from: str, period_to: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/books-periods",
        json={"period_from": period_from, "period_to": period_to},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_locked_books_period_blocks_gl_postings(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "Books Period Customer")
    period = await _create_books_period(owner_client, "2026-05-01", "2026-05-31")
    locked = await owner_client.post(f"/api/v1/books-periods/{period['id']}/lock")
    assert locked.status_code == 200

    invoice_blocked = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-05-15",
            "lines": [{"description": "Locked month", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice_blocked.status_code == 409

    outside = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-06-01",
            "lines": [{"description": "Open month", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert outside.status_code == 201


async def test_reopen_requires_reason(owner_client: AsyncClient) -> None:
    period = await _create_books_period(owner_client, "2026-07-01", "2026-07-31")
    await owner_client.post(f"/api/v1/books-periods/{period['id']}/lock")

    bad = await owner_client.post(
        f"/api/v1/books-periods/{period['id']}/reopen",
        json={"reason": "   "},
    )
    assert bad.status_code == 400

    ok = await owner_client.post(
        f"/api/v1/books-periods/{period['id']}/reopen",
        json={"reason": "Correcting May accrual"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "open"


async def test_vat201_lock_does_not_block_invoice(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _create_named_customer(owner_client, "VAT201 vs Books")
    vat_period = await _create_vat201_period(owner_client, "2026-03-01", "2026-04-30")
    await owner_client.post(f"/api/v1/vat201/periods/{vat_period['id']}/lock")

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-03-15",
            "lines": [{"description": "VAT201 locked only", "qty": 1, "unit_ex_vat": "250.00"}],
        },
    )
    assert invoice.status_code == 201
