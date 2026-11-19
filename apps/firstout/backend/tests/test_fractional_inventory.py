"""Exact stock movement through real APIs, with deliberate whole-item boundaries."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.bill import Bill, BillLine
from app.models.inventory import LocationStock
from app.models.location_bin import BinStock
from app.models.location_bin import LocationBin
from app.models.user import User
from app.models.unit_cost_audit import UnitCostAuditSource
from app.services.stock_movements import StockMovementService
from tests.pdf_fixture import MINIMAL_PDF
from app.models.purchase_order import PoLine, PurchaseOrder
from app.services.pick_allocator import ComponentNeed, LocationStockRow, allocate
from app.services.quantities import exact_quantity
from f0rge_core.exceptions import ValidationError


async def locations(client):
    response = await client.get("/api/v1/locations")
    assert response.status_code == 200
    return {row["name"]: row["id"] for row in response.json()}


async def fractional_sku(client, *, qty="0.25", suffix="STOCK", location="Kramerville"):
    location_id = (await locations(client))[location]
    response = await client.post(
        "/api/v1/skus",
        json={
            "our_ref": f"FRACTION-{suffix}",
            "our_barcode": f"FRACTION-{suffix}",
            "name": f"Fractional {suffix}",
            "design": f"Fractional {suffix}",
            "fabric": "Exact stock",
            **(
                {
                    "opening_location_id": location_id,
                    "opening_qty": qty,
                    "opening_unit_cost_zar": "100.00",
                }
                if Decimal(qty) > 0
                else {}
            ),
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), location_id


async def inventory_row(client, sku_id):
    response = await client.get("/api/v1/inventory")
    assert response.status_code == 200, response.text
    return next(row for row in response.json() if row["sku_id"] == sku_id)


async def test_fraction_survives_stock_bin_cost_report_and_home_reads(owner_client, async_db):
    sku, location_id = await fractional_sku(owner_client)
    row = await inventory_row(owner_client, sku["id"])
    assert row["on_hand"] == 0.25 and isinstance(row["on_hand"], (int, float))
    assert row["locations"][0]["bins"][0]["on_hand"] == 0.25
    assert Decimal(row["unit_cost_zar"]) == Decimal("100")
    persisted = await async_db.scalar(
        select(LocationStock).where(LocationStock.sku_id == uuid.UUID(sku["id"]))
    )
    await async_db.refresh(persisted)
    assert persisted.on_hand == Decimal("0.2500")
    bin_qty = await async_db.scalar(
        select(BinStock.on_hand).where(BinStock.sku_id == persisted.sku_id)
    )
    assert bin_qty == persisted.on_hand
    by_bin = await owner_client.get("/api/v1/stock/by-bin")
    assert by_bin.status_code == 200
    assert (
        next(item for item in by_bin.json()["items"] if item["sku_id"] == sku["id"])["on_hand"]
        == 0.25
    )
    valuation = await owner_client.get("/api/v1/reports/stock-valuation")
    assert valuation.status_code == 200
    line = next(item for item in valuation.json()["lines"] if item["sku_id"] == sku["id"])
    assert line["on_hand"] == 0.25 and Decimal(line["value_zar"]) == Decimal("25")
    assert (await owner_client.get("/api/v1/home")).json()["on_hand_qty"] == 0.25
    aged = await owner_client.get("/api/v1/reports/aged-stock")
    assert aged.status_code == 200 and aged.json()["total_qty"] == 0.25


async def test_fractional_adjustment_adds_exact_delta(owner_client):
    sku, location_id = await fractional_sku(owner_client)
    draft = await owner_client.post(
        "/api/v1/adjustments", json={"location_id": location_id, "reason": "opening"}
    )
    assert draft.status_code == 201
    line = await owner_client.post(
        f"/api/v1/adjustments/{draft.json()['id']}/lines",
        json={"sku_id": sku["id"], "qty_delta": "0.125", "unit_cost_zar": "100"},
    )
    assert line.status_code == 201, line.text
    assert line.json()["current_qty"] == 0.25 and line.json()["new_qty"] == 0.375
    done = await owner_client.post(f"/api/v1/adjustments/{draft.json()['id']}/complete")
    assert done.status_code == 200, done.text
    assert done.json()["lines"][0]["qty_delta"] == 0.125
    assert (await inventory_row(owner_client, sku["id"]))["on_hand"] == 0.375


async def test_fractional_count_completes_exact_difference(owner_client):
    sku, location_id = await fractional_sku(owner_client)
    started = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    assert started.status_code == 201
    line = next(row for row in started.json()["lines"] if row["sku_id"] == sku["id"])
    assert line["expected_qty"] == 0.25
    counted = await owner_client.patch(
        f"/api/v1/stocktakes/{started.json()['id']}/lines/{line['id']}",
        json={"counted_qty": "0.375"},
    )
    assert counted.status_code == 200 and counted.json()["variance"] == 0.125
    complete = await owner_client.post(f"/api/v1/stocktakes/{started.json()['id']}/complete")
    assert complete.status_code == 200, complete.text
    assert (await inventory_row(owner_client, sku["id"]))["on_hand"] == 0.375


async def test_fractional_transfer_preserves_sum_and_bin_rollups(owner_client, async_db):
    sku, from_id = await fractional_sku(owner_client)
    to_id = (await locations(owner_client))["Bedfordview"]
    draft = await owner_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": from_id,
            "to_location_id": to_id,
            "lines": [{"sku_id": sku["id"], "qty": "0.125"}],
        },
    )
    assert draft.status_code == 201, draft.text
    dispatched = await owner_client.post(f"/api/v1/transfers/{draft.json()['id']}/dispatch")
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["lines"][0]["qty_dispatched"] == 0.125
    received = await owner_client.post(
        f"/api/v1/transfers/{draft.json()['id']}/receive",
        json={"lines": [{"line_id": dispatched.json()["lines"][0]["id"], "qty_received": "0.125"}]},
    )
    assert received.status_code == 200, received.text
    row = await inventory_row(owner_client, sku["id"])
    assert row["on_hand"] == 0.25
    assert {item["location_id"]: item["on_hand"] for item in row["locations"]} == {
        from_id: 0.125,
        to_id: 0.125,
    }
    for item in row["locations"]:
        assert sum(Decimal(str(b["on_hand"])) for b in item["bins"]) == Decimal(
            str(item["on_hand"])
        )


@pytest.mark.parametrize("old_unknown", [True, False])
async def test_real_po_receipt_preserves_unknown_existing_cost_but_prices_fresh_stock(
    owner_client, async_db, old_unknown
):
    sku, location_id = await fractional_sku(
        owner_client, qty="3" if old_unknown else "0", suffix="RECEIPT-COST"
    )
    if old_unknown:
        row = await async_db.scalar(
            select(LocationStock).where(LocationStock.sku_id == uuid.UUID(sku["id"]))
        )
        row.unit_cost_zar = None
        await async_db.flush()
    supplier = await owner_client.post(
        "/api/v1/suppliers", json={"name": "Receipt source supplier", "default_currency": "ZAR"}
    )
    assert supplier.status_code == 201
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier.json()["id"],
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "100"}],
        },
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    assert (await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")).status_code == 200
    landed = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "1",
            "factory_invoice_number": "F",
            "factory_amount": "100",
            "factory_currency": "ZAR",
            "freight_invoice_number": "FR",
            "freight_amount": "0",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CL",
            "clearance_amount": "0",
            "clearance_currency": "ZAR",
        },
        files={
            key: ("fixture.pdf", MINIMAL_PDF, "application/pdf")
            for key in ("factory_file", "freight_file", "clearance_file")
        },
    )
    assert landed.status_code == 200, landed.text
    received = await owner_client.post(
        "/api/v1/receive", json={"purchase_order_id": po_id, "location_id": location_id}
    )
    assert received.status_code == 200, received.text
    inventory = await inventory_row(owner_client, sku["id"])
    assert inventory["on_hand"] == (4 if old_unknown else 1)
    stored = await async_db.scalar(
        select(LocationStock).where(LocationStock.sku_id == uuid.UUID(sku["id"]))
    )
    await async_db.refresh(stored)
    assert stored.unit_cost_zar is None if old_unknown else stored.unit_cost_zar == Decimal(100)
    assert (
        inventory["unit_cost_zar"] is None
        if old_unknown
        else Decimal(inventory["unit_cost_zar"]) == Decimal(100)
    )


async def test_real_known_cost_transfer_into_unknown_balance_keeps_cost_unknown(
    owner_client, async_db
):
    from tests.test_transfers import complete_location_transfer

    sku, from_id = await fractional_sku(owner_client, qty="2", suffix="TRANSFER-UNKNOWN")
    to_id = (await locations(owner_client))["Bedfordview"]
    floor = await async_db.scalar(
        select(LocationBin).where(
            LocationBin.location_id == uuid.UUID(to_id), LocationBin.is_default.is_(True)
        )
    )
    async_db.add_all(
        [
            LocationStock(
                sku_id=uuid.UUID(sku["id"]),
                location_id=uuid.UUID(to_id),
                on_hand=Decimal(3),
                unit_cost_zar=None,
            ),
            BinStock(sku_id=uuid.UUID(sku["id"]), bin_id=floor.id, on_hand=Decimal(3)),
        ]
    )
    await async_db.flush()
    await complete_location_transfer(owner_client, from_id, to_id, sku["id"], 1)
    destination = await async_db.scalar(
        select(LocationStock).where(
            LocationStock.sku_id == uuid.UUID(sku["id"]),
            LocationStock.location_id == uuid.UUID(to_id),
        )
    )
    await async_db.refresh(destination)
    assert destination.on_hand == Decimal(4) and destination.unit_cost_zar is None


async def test_unknown_incoming_cost_marks_known_existing_balance_unknown(owner_client, async_db):
    sku, location_id = await fractional_sku(owner_client, qty="3", suffix="UNKNOWN-INCOMING")
    owner = await async_db.scalar(select(User).where(User.role == "owner"))
    row = await StockMovementService(async_db).apply_incoming_qty(
        uuid.UUID(sku["id"]),
        uuid.UUID(location_id),
        Decimal(1),
        None,
        owner.id,
        UnitCostAuditSource.RECEIVE,
        "Unknown source cost",
    )
    await async_db.flush()
    await async_db.refresh(row)
    assert row.on_hand == Decimal(4) and row.unit_cost_zar is None


@pytest.mark.parametrize("value", ["0.12345", "NaN", "Infinity", "-Infinity", "10000000000"])
async def test_stock_write_apis_reject_precision_and_nonfinite_without_mutation(
    owner_client, value
):
    sku, location_id = await fractional_sku(owner_client)
    stocktake = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    line = next(row for row in stocktake.json()["lines"] if row["sku_id"] == sku["id"])
    count = await owner_client.patch(
        f"/api/v1/stocktakes/{stocktake.json()['id']}/lines/{line['id']}",
        json={"counted_qty": value},
    )
    assert count.status_code == 422, count.text
    await owner_client.post(f"/api/v1/stocktakes/{stocktake.json()['id']}/cancel")
    adjustment = await owner_client.post(
        "/api/v1/adjustments", json={"location_id": location_id, "reason": "opening"}
    )
    delta = await owner_client.post(
        f"/api/v1/adjustments/{adjustment.json()['id']}/lines",
        json={"sku_id": sku["id"], "qty_delta": value, "unit_cost_zar": "100"},
    )
    assert delta.status_code == 422, delta.text
    transfer = await owner_client.post(
        "/api/v1/transfers",
        json={
            "from_location_id": location_id,
            "to_location_id": (await locations(owner_client))["Bedfordview"],
            "lines": [{"sku_id": sku["id"], "qty": value}],
        },
    )
    assert transfer.status_code == 422, transfer.text
    assert (await inventory_row(owner_client, sku["id"]))["on_hand"] == 0.25


async def test_fractional_overdraw_rolls_back_and_nonnegative_count_is_enforced(owner_client):
    sku, location_id = await fractional_sku(owner_client)
    adjustment = await owner_client.post(
        "/api/v1/adjustments", json={"location_id": location_id, "reason": "damage"}
    )
    added = await owner_client.post(
        f"/api/v1/adjustments/{adjustment.json()['id']}/lines",
        json={"sku_id": sku["id"], "qty_delta": "-0.375"},
    )
    assert added.status_code == 201
    failed = await owner_client.post(f"/api/v1/adjustments/{adjustment.json()['id']}/complete")
    assert failed.status_code == 409
    assert (await inventory_row(owner_client, sku["id"]))["on_hand"] == 0.25
    stocktake = await owner_client.post("/api/v1/stocktakes", json={"location_id": location_id})
    line = next(row for row in stocktake.json()["lines"] if row["sku_id"] == sku["id"])
    negative = await owner_client.patch(
        f"/api/v1/stocktakes/{stocktake.json()['id']}/lines/{line['id']}",
        json={"counted_qty": "-0.125"},
    )
    assert negative.status_code == 422


def test_whole_pick_allocator_does_not_combine_fractional_locations():
    sku_id = uuid.uuid4()

    def stock(qty):
        return LocationStockRow(
            location_id=uuid.uuid4(),
            sku_id=sku_id,
            on_hand=Decimal(qty),
            location_type="warehouse",
            location_name="Fraction warehouse",
            is_archived=False,
        )

    stocks = [stock("0.5"), stock("0.5")]
    result = allocate([ComponentNeed(sku_id=sku_id, qty_needed=1)], stocks, True, [])
    assert result.lines[0].qty_allocated == 0 and result.lines[0].qty_short == 1
    assert [item.on_hand for item in stocks] == [Decimal("0.5"), Decimal("0.5")]
    whole = allocate([ComponentNeed(sku_id=sku_id, qty_needed=1)], [stock("1.25")], True, [])
    assert whole.lines[0].qty_allocated == 1 and whole.lines[0].qty_short == 0


async def test_whole_till_sale_consumes_one_and_retains_fraction(owner_client):
    sku, location_id = await fractional_sku(owner_client, qty="1.25", location="Bedfordview")
    price = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"retail_inc_vat": "115"})
    assert price.status_code == 200
    sale = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": location_id,
            "tender": "cash",
            "lines": [{"sku_id": sku["id"], "qty": 1}],
        },
    )
    assert sale.status_code == 201, sale.text
    assert sale.json()["location"]["on_hand"] == 0.25
    assert (await inventory_row(owner_client, sku["id"]))["on_hand"] == 0.25
    fractional_sale = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": location_id,
            "tender": "cash",
            "lines": [{"sku_id": sku["id"], "qty": "0.25"}],
        },
    )
    assert fractional_sale.status_code == 422


async def test_fractional_purchase_history_responses_reload_without_truncation(
    owner_client, async_db
):
    supplier = await owner_client.post(
        "/api/v1/suppliers", json={"name": "Fraction archive supplier", "default_currency": "ZAR"}
    )
    po = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier.json()["id"],
            "lines": [{"description": "Fraction source", "qty": 1, "factory_unit_amount": "100"}],
        },
    )
    assert po.status_code == 201, po.text
    po_model = await async_db.get(PurchaseOrder, uuid.UUID(po.json()["id"]))
    po_line = await async_db.get(PoLine, uuid.UUID(po.json()["lines"][0]["id"]))
    po_model.is_archive = True
    po_line.qty = Decimal("4.576")
    today = datetime.date.today().isoformat()
    bill = await owner_client.post(
        "/api/v1/bills",
        json={
            "supplier_id": supplier.json()["id"],
            "supplier_ref": "FRACTION-HISTORY",
            "issue_date": today,
            "currency": "ZAR",
            "lines": [{"description": "Fraction history", "qty": 1, "unit_amount": "100"}],
        },
    )
    assert bill.status_code == 201
    bill_model = await async_db.get(Bill, uuid.UUID(bill.json()["id"]))
    bill_line = await async_db.get(BillLine, uuid.UUID(bill.json()["lines"][0]["id"]))
    bill_model.is_archive = True
    bill_line.qty = Decimal("-3.125")
    await async_db.flush()
    await async_db.refresh(po_line)
    await async_db.refresh(bill_line)
    assert po_line.qty == Decimal("4.5760") and bill_line.qty == Decimal("-3.1250")
    assert (await owner_client.get(f"/api/v1/purchase-orders/{po.json()['id']}")).json()["lines"][
        0
    ]["qty"] == 4.576
    assert (await owner_client.get(f"/api/v1/bills/{bill.json()['id']}")).json()["lines"][0][
        "qty"
    ] == -3.125
    history = await owner_client.get("/api/v1/history/purchases")
    assert history.status_code == 200
    assert (
        next(row for row in history.json()["items"] if row["bill_id"] == bill.json()["id"])["qty"]
        == -3.125
    )


@pytest.mark.no_db
@pytest.mark.parametrize("value", ["0.12345", "NaN", "Infinity", "10000000000"])
def test_service_quantity_validation_never_rounds(value):
    with pytest.raises(ValidationError):
        exact_quantity(value)


@pytest.mark.no_db
def test_quantity_totals_accept_multiple_maximum_cells_and_keep_json_numbers():
    from pydantic import TypeAdapter
    from app.schemas.quantity import Quantity, QuantityTotal

    cell = TypeAdapter(Quantity).validate_python("9999999999.9999")
    total = cell + cell
    adapter = TypeAdapter(QuantityTotal)
    assert adapter.validate_python(total) == Decimal("19999999999.9998")
    assert Decimal(adapter.dump_json(total).decode()) == total
