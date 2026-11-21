"""Sales staff, the colleague on each till sale, and the monthly commission report."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from httpx import AsyncClient

from tests.test_purchase_orders import _create_till, _location_id_by_name, _relogin_owner
from tests.test_till_basket import BASKET, HELD, SALES, _fill, _get, _line, _stocked

STAFF = "/api/v1/sales-staff"
REPORT = "/api/v1/reports/commission"


def _month() -> str:
    return datetime.date.today().strftime("%Y-%m")


async def _staff(client: AsyncClient, name: str, **fields) -> dict:
    response = await client.post(STAFF, json={"name": name, **fields})
    assert response.status_code == 201, response.text
    return response.json()


async def _manual_invoice(client: AsyncClient, customer_id: str, amount: str) -> dict:
    response = await client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": datetime.date.today().isoformat(),
            "lines": [{"description": "Fitting", "qty": 1, "unit_ex_vat": amount}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_sales_staff_crud_and_permissions(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    thandi = await _staff(
        owner_client, "  Thandi Mokoena ", short_name="Thandi", commission_rate="2.50"
    )
    assert thandi["name"] == "Thandi Mokoena"
    assert thandi["commission_rate"] == "2.50" and thandi["is_active"] is True
    sipho = await _staff(owner_client, "Sipho Dlamini")
    assert sipho["commission_rate"] == "0.00" and sipho["short_name"] is None

    for bad in ({"name": " "}, {"name": "X", "commission_rate": "100.01"}, {"name": "X", "x": 1}):
        assert (await owner_client.post(STAFF, json=bad)).status_code == 422

    off = await owner_client.patch(f"{STAFF}/{sipho['id']}", json={"is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert (
        await owner_client.patch(f"{STAFF}/{sipho['id']}", json={"name": None})
    ).status_code == 400

    active = (await owner_client.get(STAFF, params={"status": "active"})).json()
    inactive = (await owner_client.get(STAFF, params={"status": "inactive"})).json()
    assert [row["id"] for row in active] == [thandi["id"]]
    assert [row["id"] for row in inactive] == [sipho["id"]]
    assert len((await owner_client.get(STAFF)).json()) == 2
    options = (await owner_client.get(f"{STAFF}/options")).json()
    assert options == [{"id": thandi["id"], "name": "Thandi Mokoena", "short_name": "Thandi"}]

    # An unreferenced colleague can be deleted; a missing one is 404.
    assert (await owner_client.delete(f"{STAFF}/{sipho['id']}")).status_code == 204
    assert (await owner_client.delete(f"{STAFF}/{sipho['id']}")).status_code == 404

    # The till lists names for the sale but cannot manage staff or read commission.
    till = await _create_till(async_client, owner_client)
    assert (await till.get(f"{STAFF}/options")).status_code == 200
    assert (await till.get(STAFF)).status_code == 403
    assert (await till.post(STAFF, json={"name": "Nope"})).status_code == 403
    assert (
        await till.patch(f"{STAFF}/{thandi['id']}", json={"is_active": False})
    ).status_code == 403
    assert (await till.delete(f"{STAFF}/{thandi['id']}")).status_code == 403
    assert (await till.get(REPORT, params={"month": _month()})).status_code == 403
    await _relogin_owner(owner_client)


async def test_till_requires_an_active_colleague_and_snapshots_commission_exclusion(
    owner_client: AsyncClient,
) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "COMM-SOFA", location)
    delivery = await _stocked(owner_client, "COMM-DELIVERY", location)
    flagged = await owner_client.patch(
        f"/api/v1/skus/{delivery['id']}", json={"exclude_from_commission": True}
    )
    assert flagged.status_code == 200 and flagged.json()["exclude_from_commission"] is True

    thandi = await _staff(owner_client, "Thandi", commission_rate="5")
    gone = await _staff(owner_client, "Former", is_active=False)
    sale = {
        "location_id": location,
        "lines": [_line(sofa, qty=10, discount="10"), _line(delivery, qty=5)],
        "tender": "card",
    }
    missing = await owner_client.post(SALES, json=sale)
    assert missing.status_code == 400, missing.text
    inactive = await owner_client.post(SALES, json={**sale, "sales_staff_id": gone["id"]})
    assert inactive.status_code == 400
    unknown = await owner_client.post(SALES, json={**sale, "sales_staff_id": str(uuid.uuid4())})
    assert unknown.status_code == 400

    done = await owner_client.post(SALES, json={**sale, "sales_staff_id": thandi["id"]})
    assert done.status_code == 201, done.text
    invoice_id = done.json()["invoice_id"]

    # A later SKU change leaves the issued invoice's lines as they were sold.
    await owner_client.patch(
        f"/api/v1/skus/{delivery['id']}", json={"exclude_from_commission": False}
    )
    invoice = (await owner_client.get(f"/api/v1/invoices/{invoice_id}")).json()
    assert invoice["sales_staff_id"] == thandi["id"]
    assert invoice["sales_staff_name"] == "Thandi"
    flags = {line["sku_id"]: line["exclude_from_commission"] for line in invoice["lines"]}
    assert flags == {sofa["id"]: False, delivery["id"]: True}

    # A referenced colleague cannot be deleted, only deactivated.
    assert (await owner_client.delete(f"{STAFF}/{thandi['id']}")).status_code == 409

    report = (await owner_client.get(REPORT, params={"month": _month()})).json()
    row = next(r for r in report["rows"] if r["sales_staff_id"] == thandi["id"])
    assert Decimal(row["commissionable_ex_vat"]) == Decimal("900.00")  # 1000 less 10%
    assert Decimal(row["excluded_ex_vat"]) == Decimal("500.00")


async def test_commission_report_maths_credit_notes_and_unattributed(
    owner_client: AsyncClient,
) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "COMM-R-SOFA", location)
    delivery = await _stocked(owner_client, "COMM-R-DELIVERY", location)
    await owner_client.patch(
        f"/api/v1/skus/{delivery['id']}", json={"exclude_from_commission": True}
    )
    customer = await owner_client.post("/api/v1/customers", json={"name": "Commission buyer"})
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]

    # Manual invoices before anyone is on the list: one stays unattributed.
    unattributed = await _manual_invoice(owner_client, customer_id, "400.00")
    credited = await _manual_invoice(owner_client, customer_id, "300.00")

    thandi = await _staff(owner_client, "Thandi", short_name="TM", commission_rate="5")
    sipho = await _staff(owner_client, "Sipho", commission_rate="3")
    sale = await owner_client.post(
        SALES,
        json={
            "location_id": location,
            "lines": [_line(sofa, qty=10, discount="10"), _line(delivery, qty=5)],
            "tender": "card",
            "sales_staff_id": thandi["id"],
        },
    )
    assert sale.status_code == 201, sale.text

    # Books assigns the colleague afterwards; then the invoice is credited in full.
    assigned = await owner_client.patch(
        f"/api/v1/invoices/{credited['id']}", json={"sales_staff_id": thandi["id"]}
    )
    assert assigned.status_code == 200 and assigned.json()["sales_staff_name"] == "Thandi"
    assert (
        await owner_client.patch(
            f"/api/v1/invoices/{credited['id']}", json={"sales_staff_id": str(uuid.uuid4())}
        )
    ).status_code == 404
    credit = await owner_client.post("/api/v1/credit-notes", json={"invoice_id": credited["id"]})
    assert credit.status_code == 201, credit.text

    report = await owner_client.get(REPORT, params={"month": _month()})
    assert report.status_code == 200, report.text
    body = report.json()
    rows = {row["sales_staff_id"]: row for row in body["rows"]}
    mine = rows[thandi["id"]]
    assert mine["invoice_count"] == 2
    assert Decimal(mine["commissionable_ex_vat"]) == Decimal("1200.00")  # 900 + 300
    assert Decimal(mine["excluded_ex_vat"]) == Decimal("500.00")
    assert Decimal(mine["credit_deductions"]) == Decimal("300.00")
    assert Decimal(mine["net_commissionable"]) == Decimal("900.00")
    assert Decimal(mine["commission"]) == Decimal("45.00")
    kinds = sorted((doc["kind"], doc["invoice_number"]) for doc in mine["documents"])
    assert ("credit_note", credited["invoice_number"]) in kinds
    # Active colleagues without sales still appear, at zero.
    assert rows[sipho["id"]]["invoice_count"] == 0
    assert Decimal(rows[sipho["id"]]["commission"]) == 0

    nobody = body["unattributed"]
    assert nobody["sales_staff_id"] is None and nobody["invoice_count"] == 1
    assert nobody["documents"][0]["invoice_id"] == unattributed["id"]
    assert Decimal(nobody["commissionable_ex_vat"]) == Decimal("400.00")
    assert Decimal(body["commission"]) == Decimal("45.00")
    assert Decimal(body["commissionable_ex_vat"]) == Decimal("1600.00")

    # Another month is empty; a malformed month is refused.
    empty = (await owner_client.get(REPORT, params={"month": "2001-01"})).json()
    assert empty["invoice_count"] == 0 and empty["unattributed"]["documents"] == []
    for bad in ("2026-13", "26-01", "latest"):
        assert (await owner_client.get(REPORT, params={"month": bad})).status_code in (400, 422)


async def test_basket_and_held_sale_keep_the_colleague(owner_client: AsyncClient) -> None:
    location = await _location_id_by_name(owner_client, "Bedfordview")
    sofa = await _stocked(owner_client, "COMM-HOLD", location)
    thandi = await _staff(owner_client, "Thandi")
    chosen = {"sales_staff_id": thandi["id"]}
    basket = await _fill(owner_client, await _get(owner_client, location), [_line(sofa)], **chosen)
    assert basket["sales_staff_id"] == thandi["id"]

    held = await owner_client.post(
        HELD,
        json={
            "id": str(uuid.uuid4()),
            "location_id": location,
            "lines": [_line(sofa)],
            "basket_id": basket["id"],
            **chosen,
        },
    )
    assert held.status_code == 201, held.text
    assert held.json()["sales_staff_id"] == thandi["id"]
    assert (await _get(owner_client, location))["sales_staff_id"] is None

    resumed = await owner_client.post(
        f"{HELD}/{held.json()['id']}/resume",
        json={
            "operation_id": str(uuid.uuid4()),
            "location_id": location,
            "version": held.json()["version"],
            "basket_id": basket["id"],
        },
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["basket"]["sales_staff_id"] == thandi["id"]
    assert (await owner_client.get(BASKET, params={"location_id": location})).json()[
        "sales_staff_id"
    ] == thandi["id"]


async def test_changing_the_invoice_colleague_is_in_the_books_history(
    owner_client: AsyncClient,
) -> None:
    customer = await owner_client.post("/api/v1/customers", json={"name": "History buyer"})
    assert customer.status_code == 201, customer.text
    invoice = await _manual_invoice(owner_client, customer.json()["id"], "100.00")
    thandi = await _staff(owner_client, "Thandi")
    sipho = await _staff(owner_client, "Sipho")
    url = f"/api/v1/invoices/{invoice['id']}"
    for staff_id in (thandi["id"], thandi["id"], sipho["id"], None):
        response = await owner_client.patch(url, json={"sales_staff_id": staff_id})
        assert response.status_code == 200, response.text
    # Changing only the internal note is not a colleague change.
    assert (await owner_client.patch(url, json={"note_internal": "x"})).status_code == 200

    events = await owner_client.get(
        "/api/v1/books-events",
        params={"document_type": "invoice", "document_id": invoice["id"]},
    )
    assert events.status_code == 200, events.text
    updated = [row for row in events.json() if row["action"] == "updated"]
    assert [row["note"] for row in updated] == [
        "Sales colleague: none → Thandi",
        "Sales colleague: Thandi → Sipho",
        "Sales colleague: Sipho → none",
    ]
    assert all(row["actor_email"] for row in updated)
