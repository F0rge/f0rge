"""Partial customer and supplier payments."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.journal import JournalDocumentType, JournalEntry, JournalLine
from app.nia.canvas import build_overdue_invoices_canvas_spec
from app.services.settlement import booked_portion


def test_booked_portion_keeps_the_remainder_for_the_final_slice() -> None:
    first = booked_portion(
        amount=Decimal("33.33"),
        amount_foreign=Decimal("100.00"),
        amount_zar=Decimal("100.00"),
        amount_paid_foreign=Decimal("0"),
        amount_paid_zar=Decimal("0"),
    )
    second = booked_portion(
        amount=Decimal("33.33"),
        amount_foreign=Decimal("100.00"),
        amount_zar=Decimal("100.00"),
        amount_paid_foreign=Decimal("33.33"),
        amount_paid_zar=first,
    )
    final = booked_portion(
        amount=Decimal("33.34"),
        amount_foreign=Decimal("100.00"),
        amount_zar=Decimal("100.00"),
        amount_paid_foreign=Decimal("66.66"),
        amount_paid_zar=first + second,
    )
    assert first == Decimal("33.33")
    assert second == Decimal("33.33")
    assert final == Decimal("33.34")
    assert first + second + final == Decimal("100.00")


async def _account_balances(owner_client: AsyncClient) -> dict[str, str]:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    return {account["code"]: account["balance_zar"] for account in resp.json()}


async def _create_invoice(
    owner_client: AsyncClient,
    *,
    name: str = "Partial Customer",
    issue_date: str = "2026-09-01",
    unit_ex_vat: str = "1000.00",
) -> dict:
    customer = await owner_client.post("/api/v1/customers", json={"name": name})
    assert customer.status_code == 201
    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": issue_date,
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": unit_ex_vat}],
        },
    )
    assert invoice.status_code == 201
    body = invoice.json()
    body["customer_id"] = customer.json()["id"]
    return body


async def _pay(
    owner_client: AsyncClient, invoice_id: str, amount: str, paid_on: str = "2026-09-02"
):
    return await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": invoice_id,
            "amount": amount,
            "currency": "ZAR",
            "paid_on": paid_on,
        },
    )


async def _payment_lines(async_db: AsyncSession, payment_id: str) -> list[tuple[str, str, str]]:
    rows = (
        await async_db.execute(
            select(Account.code, JournalLine.debit_zar, JournalLine.credit_zar)
            .join(JournalLine, JournalLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                JournalEntry.document_type == JournalDocumentType.PAYMENT,
                JournalEntry.document_id == UUID(payment_id),
            )
        )
    ).all()
    return sorted((code, f"{debit:.2f}", f"{credit:.2f}") for code, debit, credit in rows)


async def test_partial_then_settle_invoice(
    owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    invoice = await _create_invoice(owner_client)
    assert invoice["payment_status"] == "unpaid"
    assert invoice["balance"] == "1150.00"
    assert invoice["amount_paid"] == "0.00"

    first = await _pay(owner_client, invoice["id"], "400.00")
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["amount"] == "400.00"
    assert first_body["amount_zar"] == "400.00"

    detail = await owner_client.get(f"/api/v1/invoices/{invoice['id']}")
    assert detail.status_code == 200
    partial = detail.json()
    assert partial["amount_paid"] == "400.00"
    assert partial["balance"] == "750.00"
    assert partial["total_inc_vat"] == "1150.00"
    assert partial["payment_status"] == "partially_paid"

    balances = await _account_balances(owner_client)
    assert balances["1100"] == "400.00"
    assert balances["1200"] == "750.00"
    assert await _payment_lines(async_db, first_body["id"]) == [
        ("1100", "400.00", "0.00"),
        ("1200", "0.00", "400.00"),
    ]

    listed = await owner_client.get("/api/v1/payments", params={"invoice_id": invoice["id"]})
    assert listed.status_code == 200
    assert [item["payment_number"] for item in listed.json()["items"]] == [
        first_body["payment_number"]
    ]

    second = await _pay(owner_client, invoice["id"], "750.00", "2026-09-10")
    assert second.status_code == 201
    settled = (await owner_client.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert settled["amount_paid"] == "1150.00"
    assert settled["balance"] == "0.00"
    assert settled["payment_status"] == "paid"

    balances = await _account_balances(owner_client)
    assert balances["1100"] == "1150.00"
    assert balances["1200"] == "0.00"
    assert await _payment_lines(async_db, second.json()["id"]) == [
        ("1100", "750.00", "0.00"),
        ("1200", "0.00", "750.00"),
    ]

    history = await owner_client.get("/api/v1/payments", params={"invoice_id": invoice["id"]})
    assert [item["amount"] for item in history.json()["items"]] == ["750.00", "400.00"]

    again = await _pay(owner_client, invoice["id"], "0.01")
    assert again.status_code == 400
    assert again.json()["detail"] == "Invoice is already fully paid"


async def test_overpayment_zero_and_subcent_are_rejected(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client, name="Reject Customer")
    number = invoice["invoice_number"]

    over = await _pay(owner_client, invoice["id"], "1150.01")
    assert over.status_code == 400
    assert over.json()["detail"] == (
        f"Payment is more than the R 1,150.00 still owing on {number}."
    )

    zero = await _pay(owner_client, invoice["id"], "0")
    assert zero.status_code == 400
    assert zero.json()["detail"] == "Payment amount must be more than zero."

    negative = await _pay(owner_client, invoice["id"], "-10.00")
    assert negative.status_code == 400
    assert negative.json()["detail"] == "Payment amount must be more than zero."

    fraction = await _pay(owner_client, invoice["id"], "10.001")
    assert fraction.status_code == 400
    assert fraction.json()["detail"] == "Payment amount must be in cents."

    partial = await _pay(owner_client, invoice["id"], "100.00")
    assert partial.status_code == 201
    still_over = await _pay(owner_client, invoice["id"], "2000.00")
    assert still_over.status_code == 400
    assert still_over.json()["detail"] == (
        f"Payment is more than the R 1,050.00 still owing on {number}."
    )


async def test_three_cent_slices_settle_without_drift(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(
        owner_client,
        name="Cents Customer",
        unit_ex_vat="100.00",
    )
    assert invoice["total_inc_vat"] == "115.00"
    for amount in ("33.33", "33.33", "48.34"):
        resp = await _pay(owner_client, invoice["id"], amount)
        assert resp.status_code == 201
    settled = (await owner_client.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert settled["amount_paid"] == "115.00"
    assert settled["balance"] == "0.00"
    assert settled["payment_status"] == "paid"
    balances = await _account_balances(owner_client)
    assert balances["1200"] == "0.00"
    assert balances["1100"] == "115.00"


async def test_aged_ar_and_overdue_use_outstanding_balance(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    invoice = await _create_invoice(owner_client, name="Aged Partial Customer")
    paid = await _pay(owner_client, invoice["id"], "400.00")
    assert paid.status_code == 201

    report = await owner_client.get("/api/v1/reports/aged-ar", params={"as_of": "2026-09-15"})
    assert report.status_code == 200
    body = report.json()
    line = next(row for row in body["lines"] if row["document_number"] == invoice["invoice_number"])
    assert line["balance_zar"] == "750.00"
    assert body["total_zar"] == "750.00"

    overdue_issue = (date.today() - timedelta(days=40)).isoformat()
    overdue = await _create_invoice(
        owner_client,
        name="Overdue Partial Customer",
        issue_date=overdue_issue,
        unit_ex_vat="500.00",
    )
    assert overdue["total_inc_vat"] == "575.00"
    part = await _pay(owner_client, overdue["id"], "200.00", overdue_issue)
    assert part.status_code == 201

    customer = await owner_client.get(f"/api/v1/customers/{overdue['customer_id']}")
    assert customer.status_code == 200
    crm = customer.json()
    assert crm["open_invoices_count"] == 1
    assert crm["overdue_invoices_count"] == 1
    assert crm["open_invoices_zar"] == "375.00"
    assert crm["overdue_invoices_zar"] == "375.00"

    spec = await build_overdue_invoices_canvas_spec(async_db)
    rows = spec["components"][0]["rows"]
    match = next(row for row in rows if row[0] == overdue["invoice_number"])
    assert match[3] == "375.00"


async def test_bank_suggestion_matches_the_partial_amount(owner_client: AsyncClient) -> None:
    invoice = await _create_invoice(owner_client, name="Bank Partial Customer")
    payment = await _pay(owner_client, invoice["id"], "400.00")
    assert payment.status_code == 201
    payment_id = payment.json()["id"]

    csv_content = """Date,Description,Reference,Amount
2026-09-02,Part payment,REF001,400.00
2026-09-02,Full invoice,REF002,1150.00
"""
    uploaded = await owner_client.post(
        "/api/v1/bank-imports",
        files={"file": ("partial.csv", csv_content.encode(), "text/csv")},
    )
    assert uploaded.status_code == 201
    lines = uploaded.json()["lines"]
    assert lines[0]["suggested_payment_id"] == payment_id
    assert lines[1]["suggested_payment_id"] is None

    matched = await owner_client.post(
        f"/api/v1/bank-imports/{uploaded.json()['id']}/lines/{lines[0]['id']}/match",
        json={"payment_id": payment_id},
    )
    assert matched.status_code == 200
    assert matched.json()["matched_payment_id"] == payment_id


async def _create_usd_bill(owner_client: AsyncClient, name: str) -> dict:
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": name, "default_currency": "USD"},
    )
    assert supplier.status_code == 201
    bill = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier.json()["id"],
            "supplier_ref": "FX-PART",
            "issue_date": "2026-09-01",
            "currency": "USD",
            "fx_to_zar": "18.00",
            "lines": [{"description": "Factory invoice", "qty": 1, "unit_amount": "100.00"}],
        },
    )
    assert bill.status_code == 201
    body = bill.json()
    assert body["payment_status"] == "unpaid"
    assert body["balance_foreign"] == "100.00"
    return body


async def _pay_bill(
    owner_client: AsyncClient,
    bill_id: str,
    amount: str,
    fx_to_zar: str,
) -> object:
    return await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill_id,
            "amount": amount,
            "currency": "USD",
            "fx_to_zar": fx_to_zar,
            "paid_on": "2026-09-03",
        },
    )


async def test_partial_bill_payments_post_only_the_cleared_slice(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    bill = await _create_usd_bill(owner_client, "Partial FX Supplier")
    first = await _pay_bill(owner_client, bill["id"], "40.00", "19.00")
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["amount_zar"] == "760.00"
    assert first_body["fx_gain_loss_zar"] == "-40.00"
    assert await _payment_lines(async_db, first_body["id"]) == [
        ("1100", "0.00", "760.00"),
        ("2100", "720.00", "0.00"),
        ("6100", "40.00", "0.00"),
    ]

    detail = (await owner_client.get(f"/api/v1/bills/{bill['id']}")).json()
    assert detail["amount_paid_foreign"] == "40.00"
    assert detail["balance_foreign"] == "60.00"
    assert detail["amount_paid_zar"] == "720.00"
    assert detail["balance_zar"] == "1080.00"
    assert detail["payment_status"] == "partially_paid"

    over = await _pay_bill(owner_client, bill["id"], "60.01", "17.00")
    assert over.status_code == 400
    assert over.json()["detail"] == (
        f"Payment is more than the USD 60.00 still owing on {bill['bill_number']}."
    )

    second = await _pay_bill(owner_client, bill["id"], "60.00", "17.00")
    assert second.status_code == 201
    assert second.json()["amount_zar"] == "1020.00"
    assert second.json()["fx_gain_loss_zar"] == "60.00"
    assert await _payment_lines(async_db, second.json()["id"]) == [
        ("1100", "0.00", "1020.00"),
        ("2100", "1080.00", "0.00"),
        ("6100", "0.00", "60.00"),
    ]

    settled = (await owner_client.get(f"/api/v1/bills/{bill['id']}")).json()
    assert settled["payment_status"] == "paid"
    assert settled["balance_foreign"] == "0.00"
    assert settled["balance_zar"] == "0.00"
    assert settled["amount_paid_zar"] == "1800.00"
    balances = await _account_balances(owner_client)
    assert balances["2100"] == "0.00"


async def test_zar_bill_accepts_a_partial_payment(owner_client: AsyncClient) -> None:
    supplier = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Local Partial Supplier", "default_currency": "ZAR"},
    )
    assert supplier.status_code == 201
    bill = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier.json()["id"],
            "supplier_ref": "LOCAL-1",
            "issue_date": "2026-09-01",
            "currency": "ZAR",
            "lines": [{"description": "Delivery", "qty": 1, "unit_amount": "50.00"}],
        },
    )
    assert bill.status_code == 201
    bill_body = bill.json()
    payment = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "out",
            "bill_id": bill_body["id"],
            "amount": "20.00",
            "currency": "ZAR",
            "paid_on": "2026-09-04",
        },
    )
    assert payment.status_code == 201
    assert payment.json()["fx_gain_loss_zar"] == "0.00"
    detail = (await owner_client.get(f"/api/v1/bills/{bill_body['id']}")).json()
    assert detail["payment_status"] == "partially_paid"
    assert detail["balance_zar"] == "30.00"
    assert detail["balance_foreign"] == "30.00"
