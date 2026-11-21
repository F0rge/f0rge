"""Pay on statement at the till: the invoice is issued unpaid, on account, with no payment."""

from __future__ import annotations

import datetime
import uuid

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.journal import JournalDocumentType, JournalEntry
from app.models.payment import Payment
from tests.test_purchase_orders import _create_till, _relogin_owner
from tests.test_till import _ready_showroom_sale


async def _payment_journal_count(client: AsyncClient) -> int:
    return (
        await client.test_db.execute(
            select(func.count())
            .select_from(JournalEntry)
            .where(JournalEntry.document_type == JournalDocumentType.PAYMENT)
        )
    ).scalar_one()


async def test_statement_sale_issues_unpaid_invoice_without_payment(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-STMT-1")
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Statement Customer", "payment_terms_days": 14},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    # Statement sales take any customer: a credit hold does not block them.
    held = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"on_hold": True, "credit_limit": "1.00"},
    )
    assert held.status_code == 200
    journals_before = await _payment_journal_count(owner_client)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "statement",
            "customer_id": customer_id,
        },
    )
    assert sale.status_code == 201, sale.text
    body = sale.json()
    today = datetime.date.today()
    assert body["tender"] == "statement"
    assert body["on_account"] is True
    assert body["payment_id"] is None
    assert body["payment_number"] is None
    assert body["due_date"] == (today + datetime.timedelta(days=14)).isoformat()
    assert body["location"]["on_hand"] == 0

    invoice = await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")
    assert invoice.status_code == 200
    payload = invoice.json()
    assert payload["on_account"] is True
    assert payload["payment_status"] == "unpaid"
    assert payload["amount_paid"] == "0.00"
    assert payload["balance"] == payload["total_inc_vat"]

    payments = (
        await owner_client.test_db.execute(
            select(Payment).where(Payment.invoice_id == uuid.UUID(body["invoice_id"]))
        )
    ).all()
    assert payments == []
    assert await _payment_journal_count(owner_client) == journals_before

    # Settled later through the invoice's Record payment.
    await _relogin_owner(owner_client)
    paid = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": body["invoice_id"],
            "amount": payload["total_inc_vat"],
            "currency": "ZAR",
            "paid_on": today.isoformat(),
        },
    )
    assert paid.status_code == 201, paid.text
    settled = (await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")).json()
    assert settled["payment_status"] == "paid"
    assert settled["balance"] == "0.00"
    assert settled["on_account"] is True


async def test_statement_sale_takes_due_date_and_rejects_one_before_issue(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-STMT-2")
    till = await _create_till(async_client, owner_client)
    today = datetime.date.today()
    sale = {
        "location_id": bedford_id,
        "lines": [{"sku_id": sku_id, "qty": 1}],
        "tender": "statement",
    }

    early = await till.post(
        "/api/v1/till/sales",
        json={**sale, "due_date": (today - datetime.timedelta(days=1)).isoformat()},
    )
    assert early.status_code == 400
    assert early.json()["detail"] == "Due date cannot be before the issue date"

    due = (today + datetime.timedelta(days=45)).isoformat()
    ok = await till.post("/api/v1/till/sales", json={**sale, "due_date": due})
    assert ok.status_code == 201, ok.text
    assert ok.json()["due_date"] == due
    await _relogin_owner(owner_client)
    listed = await owner_client.get("/api/v1/invoices")
    row = next(item for item in listed.json()["items"] if item["id"] == ok.json()["invoice_id"])
    assert row["on_account"] is True
    assert row["due_date"] == due


async def test_card_sale_is_not_on_account(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _ready_showroom_sale(async_client, owner_client, "TILL-STMT-3")
    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={"location_id": bedford_id, "lines": [{"sku_id": sku_id, "qty": 1}], "tender": "card"},
    )
    assert sale.status_code == 201
    body = sale.json()
    assert body["on_account"] is False
    await _relogin_owner(owner_client)
    assert body["payment_number"].startswith("PAY-")
    invoice = (await owner_client.get(f"/api/v1/invoices/{body['invoice_id']}")).json()
    assert invoice["on_account"] is False
    assert invoice["payment_status"] == "paid"
