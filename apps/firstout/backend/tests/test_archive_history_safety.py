"""Imported source history cannot become live debt or reconstructed correspondence."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.models.bill import Bill, BillLine
from app.models.comms_message import CommsMessage
from app.models.journal import JournalEntry
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.object_storage import save_bytes
from tests.pdf_fixture import MINIMAL_PDF


async def test_archive_api_history_readable_but_live_debt_pdf_and_comms_are_blocked(
    owner_client, async_db, monkeypatch
):
    customer = (
        await owner_client.post(
            "/api/v1/customers",
            json={"name": "Source history customer", "email": "history@example.com"},
        )
    ).json()
    supplier = (
        await owner_client.post(
            "/api/v1/suppliers", json={"name": "Source history supplier", "default_currency": "ZAR"}
        )
    ).json()
    live_invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer["id"],
            "issue_date": "2026-11-14",
            "lines": [{"description": "Current sale", "qty": 1, "unit_ex_vat": "100"}],
        },
    )
    assert live_invoice.status_code == 201 and live_invoice.json()["is_archive"] is False
    bill_data = {
        "supplier_id": supplier["id"],
        "supplier_ref": "CURRENT",
        "issue_date": "2026-11-14",
        "currency": "ZAR",
        "lines": [{"description": "Current purchase", "qty": 1, "unit_amount": "200"}],
    }
    live_bill = await owner_client.post("/api/v1/bills", json=bill_data)
    assert (
        live_bill.status_code == 201
        and live_bill.json()["is_archive"] is False
        and live_bill.json()["fx_rate_known"] is True
    )
    journal_before = await async_db.scalar(select(func.count()).select_from(JournalEntry))
    invoice = TaxInvoice(
        invoice_number="SOURCE-HISTORY-INV",
        customer_id=uuid.UUID(customer["id"]),
        issue_date=datetime.date(2025, 1, 1),
        subtotal_ex_vat=Decimal(200),
        vat_amount=Decimal(30),
        total_inc_vat=Decimal(230),
        amount_paid=Decimal(0),
        is_archive=True,
        lines=[
            InvoiceLine(
                description="Source invoice line",
                qty=1,
                unit_ex_vat=Decimal(200),
                ex_vat=Decimal(200),
                vat_amount=Decimal(30),
                inc_vat=Decimal(230),
                sort_order=0,
            )
        ],
    )
    bills = [
        Bill(
            bill_number=f"CIN7-SOURCE-HISTORY-{index}",
            supplier_id=uuid.UUID(supplier["id"]),
            supplier_ref="ORIGINAL-REF",
            issue_date=datetime.date(2025, index, 1),
            currency="USD",
            fx_to_zar=Decimal(0),
            fx_rate_known=False,
            amount_foreign=Decimal(115),
            amount_zar=Decimal(0),
            amount_paid_zar=Decimal(0),
            amount_paid_foreign=Decimal(0),
            is_archive=True,
            cin7_source_payload={
                "format": "cin7-prepared-v1",
                "rows": [{"Quantity": "4.576", "Total": "115.00"}],
            },
            lines=[
                BillLine(
                    description="Source purchase line",
                    qty=Decimal("4.576"),
                    unit_amount=Decimal("25.13"),
                    amount_foreign=Decimal(115),
                    sort_order=0,
                )
            ],
        )
        for index in (1, 2)
    ]
    async_db.add_all([invoice, *bills])
    await async_db.flush()
    assert await async_db.scalar(select(func.count()).select_from(JournalEntry)) == journal_before

    invoices = (await owner_client.get("/api/v1/invoices")).json()
    purchases = (await owner_client.get("/api/v1/bills")).json()
    assert {row["id"] for row in invoices["items"]} == {live_invoice.json()["id"]}
    assert {row["id"] for row in purchases["items"]} == {live_bill.json()["id"]}
    assert (await owner_client.get("/api/v1/invoices", params={"q": "SOURCE-HISTORY"})).json()[
        "total"
    ] == 0
    assert (await owner_client.get("/api/v1/bills", params={"q": "ORIGINAL-REF"})).json()[
        "total"
    ] == 0
    detail = (await owner_client.get(f"/api/v1/invoices/{invoice.id}")).json()
    assert detail["is_archive"] is True and detail["payment_status"] == "unknown"
    assert Decimal(detail["total_inc_vat"]) == Decimal("230.00") and Decimal(
        detail["lines"][0]["ex_vat"]
    ) == Decimal("200.00")
    bill_detail = (await owner_client.get(f"/api/v1/bills/{bills[0].id}")).json()
    assert (
        bill_detail["is_archive"] is True
        and bill_detail["payment_status"] == "unknown"
        and bill_detail["fx_rate_known"] is False
    )
    assert (
        Decimal(bill_detail["amount_foreign"]) == Decimal("115.00")
        and bill_detail["lines"][0]["qty"] == 4.576
    )
    sales_history = (
        await owner_client.get("/api/v1/history/sales", params={"q": "SOURCE-HISTORY-INV"})
    ).json()
    purchase_history = (
        await owner_client.get("/api/v1/history/purchases", params={"q": "ORIGINAL-REF"})
    ).json()
    assert sales_history["total"] == 1 and Decimal(sales_history["items"][0]["inc_vat"]) == Decimal(
        "230.00"
    )
    assert purchase_history["total"] == 2 and {
        r["bill_number"] for r in purchase_history["items"]
    } == {"ORIGINAL-REF"}
    assert all(
        r["bill_amount_zar"] is None and r["fx_rate_known"] is False
        for r in purchase_history["items"]
    )
    assert all(
        r["unit_amount"] is None and Decimal(r["amount_foreign"]) == Decimal("115.00")
        for r in purchase_history["items"]
    )
    ar = (await owner_client.get("/api/v1/reports/aged-ar", params={"as_of": "2026-11-14"})).json()
    ap = (await owner_client.get("/api/v1/reports/aged-ap", params={"as_of": "2026-11-14"})).json()
    assert {r["document_number"] for r in ar["lines"]} == {live_invoice.json()["invoice_number"]}
    assert {r["document_number"] for r in ap["lines"]} == {live_bill.json()["bill_number"]}

    async def unexpected_delivery(*_args, **_kwargs):
        raise AssertionError("Archived document reached a communications provider")

    monkeypatch.setattr("app.services.comms.send.send_message", unexpected_delivery)
    monkeypatch.setattr("app.services.comms.send.send_cloud_document", unexpected_delivery)
    assert (await owner_client.get(f"/api/v1/invoices/{invoice.id}/pdf")).status_code == 409
    for channel in ("email", "whatsapp"):
        assert (
            await owner_client.post(
                f"/api/v1/invoices/{invoice.id}/send", json={"channel": channel}
            )
        ).status_code == 409
    assert (
        await owner_client.post(
            "/api/v1/payment-reminders/send-now",
            json={"invoice_id": str(invoice.id), "offset_days": 0},
        )
    ).status_code == 409
    assert (
        await owner_client.post(f"/api/v1/payment-reminders/invoices/{invoice.id}/pause")
    ).status_code == 409
    assert await async_db.scalar(select(func.count()).select_from(CommsMessage)) == 0
    assert (
        await owner_client.post(
            f"/api/v1/bills/{bills[0].id}/attachment",
            files={"file": ("new.pdf", MINIMAL_PDF, "application/pdf")},
        )
    ).status_code == 409
    assert (await owner_client.get(f"/api/v1/bills/{bills[0].id}/attachment")).status_code == 404
    # A retained original attachment is still available without reconstructing it.
    bills[0].pdf_storage_key = save_bytes("synthetic/source-original.pdf", MINIMAL_PDF)
    await async_db.flush()
    original = await owner_client.get(f"/api/v1/bills/{bills[0].id}/attachment")
    assert original.status_code == 200 and original.content == MINIMAL_PDF

    # Archive references do not participate in the live invoice uniqueness rule.
    followup = await owner_client.post(
        "/api/v1/bills", json={**bill_data, "supplier_ref": "ORIGINAL-REF"}
    )
    assert followup.status_code == 201 and followup.json()["is_archive"] is False
    duplicate = await owner_client.post(
        "/api/v1/bills", json={**bill_data, "supplier_ref": "ORIGINAL-REF"}
    )
    assert duplicate.status_code == 409
