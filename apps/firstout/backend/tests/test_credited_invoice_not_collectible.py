"""A fully credited invoice is not outstanding debt."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient


async def test_fully_credited_invoice_is_not_collectible(owner_client: AsyncClient) -> None:
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Credited Limit Customer"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    limited = await owner_client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"credit_limit": "115.00"},
    )
    assert limited.status_code == 200

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [{"description": "Sofa", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert invoice.status_code == 201
    invoice_body = invoice.json()
    assert invoice_body["total_inc_vat"] == "115.00"
    assert invoice_body["balance"] == "115.00"

    credit = await owner_client.post(
        "/api/v1/credit-notes",
        json={"invoice_id": invoice_body["id"], "reason": "Returned"},
    )
    assert credit.status_code == 201
    assert credit.json()["total_inc_vat"] == "115.00"

    detail = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert detail.status_code == 200
    assert detail.json()["open_invoices_count"] == 0
    assert detail.json()["open_invoices_zar"] == "0.00"
    assert detail.json()["overdue_invoices_count"] == 0
    assert detail.json()["overdue_invoices_zar"] == "0.00"

    aged = await owner_client.get(
        "/api/v1/reports/aged-ar",
        params={"as_of": "2026-10-11"},
    )
    assert aged.status_code == 200
    aged_body = aged.json()
    assert Decimal(aged_body["total_zar"]) == Decimal("0.00")
    assert all(
        line["document_number"] != invoice_body["invoice_number"] for line in aged_body["lines"]
    )

    reminders = await owner_client.get("/api/v1/payment-reminders")
    assert reminders.status_code == 200
    board = reminders.json()
    chased = [row["invoice_number"] for key in ("upcoming", "due", "held") for row in board[key]]
    assert invoice_body["invoice_number"] not in chased
    assert all(row["invoice_id"] != invoice_body["id"] for row in board["needs_attention"])

    reloaded = await owner_client.get(f"/api/v1/invoices/{invoice_body['id']}")
    assert reloaded.status_code == 200
    assert reloaded.json()["amount_paid"] == "0.00"
    assert reloaded.json()["balance"] == "0.00"

    later = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-10-02",
            "lines": [{"description": "Second sofa", "qty": 1, "unit_ex_vat": "100.00"}],
        },
    )
    assert later.status_code == 201, later.text

    payment = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice_body["id"],
            "amount": "115.00",
            "currency": "ZAR",
            "paid_on": "2026-10-02",
        },
    )
    assert payment.status_code == 400
