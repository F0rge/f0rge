"""B8 append-only books document history (#569)."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import settings


async def _account_ids(client: AsyncClient) -> dict[str, str]:
    resp = await client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["id"] for account in resp.json()}


def _manual_body(accounts: dict[str, str]) -> dict:
    return {
        "entry_date": "2026-09-01",
        "memo": "Rent",
        "source": "manual",
        "status": "posted",
        "lines": [
            {"account_id": accounts["5000"], "debit_zar": "100.00", "credit_zar": "0.00"},
            {"account_id": accounts["1100"], "debit_zar": "0.00", "credit_zar": "100.00"},
        ],
    }


async def test_posted_journal_then_void_leaves_two_history_rows(
    owner_client: AsyncClient,
) -> None:
    accounts = await _account_ids(owner_client)
    created = await owner_client.post("/api/v1/journals", json=_manual_body(accounts))
    assert created.status_code == 201
    journal_id = created.json()["id"]

    voided = await owner_client.post(f"/api/v1/journals/{journal_id}/void")
    assert voided.status_code == 200

    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "journal", "document_id": journal_id},
    )
    assert events.status_code == 200
    rows = events.json()
    assert len(rows) == 2
    assert [row["action"] for row in rows] == ["posted", "voided"]
    assert all(row["document_type"] == "journal" for row in rows)
    assert all(row["document_id"] == journal_id for row in rows)
    assert rows[0]["actor_email"] == settings.seed_owner_email

    patch_resp = await owner_client.patch(
        f"/api/v1/books-events/{rows[0]['id']}",
        json={"note": "edited"},
    )
    assert patch_resp.status_code in (404, 405)


async def test_create_invoice_records_one_created_event(
    owner_client: AsyncClient,
) -> None:
    customer = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Books Event Customer"},
    )
    assert customer.status_code == 201
    created = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Table", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert created.status_code == 201
    invoice_id = created.json()["id"]

    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "invoice", "document_id": invoice_id},
    )
    assert events.status_code == 200
    rows = events.json()
    assert len(rows) == 1
    assert rows[0]["action"] == "created"
    assert rows[0]["document_type"] == "invoice"
    assert rows[0]["document_id"] == invoice_id
    assert rows[0]["actor_email"] == settings.seed_owner_email


async def test_unauthenticated_books_events_returns_401(async_client: AsyncClient) -> None:
    resp = await async_client.get(
        "/api/v1/books-events",
        params={
            "document_type": "journal",
            "document_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert resp.status_code == 401
