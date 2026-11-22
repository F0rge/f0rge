"""Manual invoices built like the till, staff archiving, and the invoices workspace."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_invoice import InvoiceLine, TaxInvoice
from tests.conftest import authenticate_as, create_test_staff
from tests.test_purchase_orders import _location_id_by_name
from tests.test_till_basket import SALES, _line, _stocked

TODAY = datetime.date.today()
INVOICES = "/api/v1/invoices"
WORKSPACE = "/api/v1/record-workspaces/invoices/query"


async def _customer(client: AsyncClient, name: str) -> str:
    response = await client.post("/api/v1/customers", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _free(description: str, unit: str, qty: int = 1) -> dict:
    return {"description": description, "qty": qty, "unit_ex_vat": unit}


async def _invoice(client: AsyncClient, customer_id: str, lines: list[dict], **extra) -> dict:
    response = await client.post(
        INVOICES,
        json={"customer_id": customer_id, "issue_date": TODAY.isoformat(), "lines": lines, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _ids(client: AsyncClient, **query) -> list[str]:
    response = await client.post(WORKSPACE, json={"limit": 100, **query})
    assert response.status_code == 200, response.text
    return [row["id"] for row in response.json()["items"]]


async def test_manual_invoice_prices_sku_and_free_text_lines_like_the_till(
    owner_client: AsyncClient,
) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "INV-MAN-SOFA", location)
    delivery = await _stocked(owner_client, "INV-MAN-DELIVERY", location)
    patched = await owner_client.patch(
        f"/api/v1/skus/{delivery['id']}", json={"exclude_from_commission": True}
    )
    assert patched.status_code == 200
    customer_id = await _customer(owner_client, "Manual invoice buyer")
    staff = await owner_client.post("/api/v1/sales-staff", json={"name": "Lerato"})
    assert staff.status_code == 201, staff.text
    lines = [
        {"description": "Sofa", "sku_id": sofa["id"], "qty": 2, "discount_percent": "10"},
        {"description": "Delivery", "sku_id": delivery["id"], "qty": 1},
        _free("Assembly", "25.50", qty=3),
    ]

    # As at the till: once colleagues are on the list, the invoice names one.
    missing = await owner_client.post(
        INVOICES,
        json={"customer_id": customer_id, "issue_date": TODAY.isoformat(), "lines": lines},
    )
    assert missing.status_code == 400 and "sales colleague" in missing.json()["detail"]

    preview = await owner_client.post(
        f"{INVOICES}/preview", json={"customer_id": customer_id, "lines": lines}
    )
    assert preview.status_code == 200, preview.text
    priced = preview.json()
    # Every line is listed, in cart order: the browser never prices a line itself.
    assert [line["sku_id"] for line in priced["lines"]] == [sofa["id"], delivery["id"], None]
    assert [line["ex_vat"] for line in priced["lines"]] == ["180.00", "100.00", "76.50"]
    assert Decimal(priced["subtotal_ex_vat"]) == Decimal("356.50")  # 180 + 100 + 76.50

    invoice = await _invoice(
        owner_client,
        customer_id,
        lines,
        sales_staff_id=staff.json()["id"],
        note_printed="Deliver after 2pm",
        note_internal="Paid deposit in store",
    )
    assert Decimal(invoice["subtotal_ex_vat"]) == Decimal(priced["subtotal_ex_vat"])
    assert Decimal(invoice["total_inc_vat"]) == Decimal(priced["total_inc_vat"])
    assert invoice["on_account"] is True and invoice["status"] == "on_statement"
    assert invoice["source"] == "manual" and invoice["is_archived"] is False
    assert invoice["sales_staff_name"] == "Lerato"
    assert invoice["note_printed"] == "Deliver after 2pm"
    assert invoice["due_date"] >= invoice["issue_date"]
    assert [
        (
            line["description"],
            line["sku_id"],
            Decimal(line["unit_ex_vat"]),
            Decimal(line["discount_percent"]),
            Decimal(line["ex_vat"]),
            line["exclude_from_commission"],
        )
        for line in invoice["lines"]
    ] == [
        # The list unit and the discount, not a discounted unit (ADR 0001).
        ("Sofa", sofa["id"], Decimal("100"), Decimal("10"), Decimal("180"), False),
        ("Delivery", delivery["id"], Decimal("100"), Decimal("0"), Decimal("100"), True),
        ("Assembly", None, Decimal("25.50"), Decimal("0"), Decimal("76.50"), False),
    ]


async def test_already_paid_records_the_payment_with_method_and_reference(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _customer(owner_client, "Paid invoice buyer")
    due = (TODAY + datetime.timedelta(days=5)).isoformat()
    invoice = await _invoice(
        owner_client,
        customer_id,
        [_free("Fitting", "200.00")],
        due_date=due,
        payment={"tender": "eft", "reference": " EFT-123 ", "paid_on": TODAY.isoformat()},
    )
    assert invoice["status"] == "paid" and invoice["on_account"] is False
    assert invoice["due_date"] == due and Decimal(invoice["balance"]) == 0

    payments = await owner_client.get("/api/v1/payments", params={"invoice_id": invoice["id"]})
    [payment] = payments.json()["items"]
    assert payment["tender"] == "eft" and payment["reference"] == "EFT-123"
    assert Decimal(payment["amount"]) == Decimal(invoice["total_inc_vat"])

    early = await owner_client.post(
        INVOICES,
        json={
            "customer_id": customer_id,
            "issue_date": TODAY.isoformat(),
            "due_date": (TODAY - datetime.timedelta(days=1)).isoformat(),
            "lines": [_free("Fitting", "200.00")],
        },
    )
    assert early.status_code == 422


async def test_archive_restore_lifecycle_status_filters_and_kpis(
    async_client: AsyncClient, owner_client: AsyncClient, async_db: AsyncSession
) -> None:
    customer_id = await _customer(owner_client, "Archive buyer")
    overdue = await _invoice(
        owner_client,
        customer_id,
        [_free("Repair", "100.00")],
        issue_date=(TODAY - datetime.timedelta(days=10)).isoformat(),
        due_date=(TODAY - datetime.timedelta(days=1)).isoformat(),
    )
    paid = await _invoice(
        owner_client,
        customer_id,
        [_free("Cushions", "50.00")],
        payment={"tender": "card", "paid_on": TODAY.isoformat()},
    )
    location = await _location_id_by_name(owner_client, "Bedfordview")
    chair = await _stocked(owner_client, "INV-ARCH-CHAIR", location)
    sale = await owner_client.post(
        SALES, json={"location_id": location, "lines": [_line(chair, qty=1)], "tender": "card"}
    )
    assert sale.status_code == 201, sale.text
    till_id = sale.json()["invoice_id"]
    imported = TaxInvoice(
        invoice_number="CIN7-ARCHIVE-1",
        customer_id=uuid.UUID(customer_id),
        issue_date=datetime.date(2025, 1, 1),
        subtotal_ex_vat=Decimal(100),
        vat_amount=Decimal(15),
        total_inc_vat=Decimal(115),
        vat_rate=Decimal("0.15"),
        amount_paid=Decimal(0),
        is_archive=True,
        lines=[
            InvoiceLine(
                description="Imported line",
                qty=1,
                unit_ex_vat=Decimal(100),
                ex_vat=Decimal(100),
                vat_amount=Decimal(15),
                inc_vat=Decimal(115),
            )
        ],
    )
    async_db.add(imported)
    await async_db.flush()

    rows = (await owner_client.post(WORKSPACE, json={"limit": 100})).json()["items"]
    sources = {row["id"]: (row["source"], row["status"]) for row in rows}
    assert sources == {
        overdue["id"]: ("manual", "overdue"),
        paid["id"]: ("manual", "paid"),
        till_id: ("till", "paid"),
        str(imported.id): ("imported", "unknown"),
    }
    overdue_filter = {"filters": [{"field": "status", "operator": "eq", "value": "overdue"}]}
    assert await _ids(owner_client, **overdue_filter) == [overdue["id"]]

    summary = (await owner_client.get(f"{INVOICES}/summary")).json()
    assert summary["outstanding_count"] == 1 and summary["overdue_count"] == 1
    assert Decimal(summary["outstanding_zar"]) == Decimal("115.00")
    assert summary["on_statement_count"] == 0 and summary["paid_this_month_count"] == 2

    archived = await owner_client.post(f"{INVOICES}/{overdue['id']}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True and archived.json()["archived_at"]
    assert (await owner_client.post(f"{INVOICES}/{overdue['id']}/archive")).status_code == 400
    assert overdue["id"] not in await _ids(owner_client)
    assert await _ids(owner_client, lifecycle="archived") == [overdue["id"]]
    counts = (await owner_client.post(WORKSPACE, json={})).json()["counts"]
    assert counts == {"active": 3, "archived": 1}
    # Still owed and still in the books: archiving only hides it from the list.
    assert (await owner_client.get(f"{INVOICES}/summary")).json()["overdue_count"] == 1
    payment = await owner_client.post(
        "/api/v1/payments",
        json={
            "direction": "in",
            "invoice_id": overdue["id"],
            "amount": "10.00",
            "currency": "ZAR",
            "paid_on": TODAY.isoformat(),
        },
    )
    assert payment.status_code == 201, payment.text

    assert (await owner_client.post(f"{INVOICES}/{imported.id}/archive")).status_code == 409
    restored = await owner_client.post(f"{INVOICES}/{overdue['id']}/restore")
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    assert (await owner_client.post(f"{INVOICES}/{overdue['id']}/restore")).status_code == 400

    await create_test_staff(owner_client, email="till-invoices@example.com", role="till")
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "till-invoices@example.com")).status_code == 200
    assert (await async_client.post(f"{INVOICES}/{overdue['id']}/archive")).status_code == 403
    assert (
        await async_client.post(
            f"{INVOICES}/preview",
            json={"customer_id": customer_id, "lines": [_free("Repair", "100.00")]},
        )
    ).status_code == 403
    # Reading invoices stays open to staff.
    assert (await async_client.get(f"{INVOICES}/summary")).status_code == 200
    assert (await async_client.post(WORKSPACE, json={})).status_code == 200


async def test_line_discounts_need_the_till_discount_permission(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    customer_id = await _customer(owner_client, "Discount buyer")
    await create_test_staff(owner_client, email="books-invoices@example.com", role="books")
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "books-invoices@example.com")).status_code == 200
    line = {**_free("Repair", "100.00"), "discount_percent": "5"}
    refused = await async_client.post(
        INVOICES,
        json={"customer_id": customer_id, "issue_date": TODAY.isoformat(), "lines": [line]},
    )
    assert refused.status_code == 403
    allowed = await async_client.post(
        INVOICES,
        json={
            "customer_id": customer_id,
            "issue_date": TODAY.isoformat(),
            "lines": [_free("Repair", "100.00")],
        },
    )
    assert allowed.status_code == 201, allowed.text


async def test_product_lines_cannot_carry_a_typed_unit(owner_client: AsyncClient) -> None:
    # A typed unit on a SKU line would bypass the till.discount check on discount_percent.
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "INV-TYPED-SOFA", location)
    customer_id = await _customer(owner_client, "Typed unit buyer")
    lines = [{"description": "Sofa", "sku_id": sofa["id"], "qty": 1, "unit_ex_vat": "1.00"}]

    preview = await owner_client.post(
        f"{INVOICES}/preview", json={"customer_id": customer_id, "lines": lines}
    )
    created = await owner_client.post(
        INVOICES,
        json={"customer_id": customer_id, "issue_date": TODAY.isoformat(), "lines": lines},
    )
    for response in (preview, created):
        assert response.status_code == 422, response.text
        assert "priced from the catalogue" in response.text


async def test_already_paid_invoice_and_payment_commit_together(
    owner_client: AsyncClient,
) -> None:
    customer_id = await _customer(owner_client, "Atomic buyer")
    on_account = await _invoice(
        owner_client,
        customer_id,
        [_free("Repair", "100.00")],
        due_date=(TODAY + datetime.timedelta(days=30)).isoformat(),
    )
    summary = (await owner_client.get(f"{INVOICES}/summary")).json()
    assert summary["on_statement_count"] == 1 and summary["outstanding_count"] == 1
    assert Decimal(summary["on_statement_zar"]) == Decimal(on_account["total_inc_vat"])

    issued, paid_on = datetime.date(2024, 1, 10), datetime.date(2024, 2, 10)
    period = await owner_client.post(
        "/api/v1/books-periods", json={"period_from": "2024-02-01", "period_to": "2024-02-29"}
    )
    assert period.status_code == 201, period.text
    locked = await owner_client.post(f"/api/v1/books-periods/{period.json()['id']}/lock")
    assert locked.status_code == 200, locked.text

    def body(paid: datetime.date) -> dict:
        return {
            "customer_id": customer_id,
            "issue_date": issued.isoformat(),
            "lines": [_free("Fitting", "200.00")],
            "payment": {"tender": "eft", "paid_on": paid.isoformat()},
        }

    # The invoice date is open but the payment date is locked: nothing is created.
    refused = await owner_client.post(INVOICES, json=body(paid_on))
    assert refused.status_code == 409, refused.text
    early = await owner_client.post(INVOICES, json=body(issued - datetime.timedelta(days=1)))
    assert early.status_code == 422 and "Paid on" in early.text
    assert await _ids(owner_client) == [on_account["id"]]
    assert (await owner_client.get(f"{INVOICES}/summary")).json() == summary
