"""F7 actual lead-time stamps and supplier/SKU reports."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.purchase_order import PurchaseOrder
from app.models.sku import Sku
from app.services.lead_times import median_days
from tests.test_purchase_orders import (
    MINIMAL_PDF,
    _create_sku,
    _create_supplier,
    _location_id_by_name,
    _relogin_owner,
)

LAND_DATA = {
    "fx_to_zar": "18.50",
    "factory_invoice_number": "F",
    "factory_amount": "100.00",
    "factory_currency": "USD",
    "freight_invoice_number": "FR",
    "freight_amount": "10.00",
    "freight_currency": "ZAR",
    "clearance_invoice_number": "CL",
    "clearance_amount": "5.00",
    "clearance_currency": "USD",
}

LAND_FILES = {
    "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
    "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
    "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
}


def test_median_10_20_100_is_20() -> None:
    assert median_days([10, 20, 100]) == 20


def _parse_dt(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _as_naive_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def _utc(year: int, month: int, day: int) -> datetime.datetime:
    return datetime.datetime(year, month, day, 12, 0, tzinfo=datetime.timezone.utc)


async def _land(client: AsyncClient, po_id: str) -> None:
    resp = await client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data=LAND_DATA,
        files=LAND_FILES,
    )
    assert resp.status_code == 200


async def _receive(client: AsyncClient, po_id: str) -> dict:
    location_id = await _location_id_by_name(client, "Kramerville")
    resp = await client.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location_id},
    )
    assert resp.status_code == 200
    return resp.json()


async def _create_open_po(
    client: AsyncClient,
    *,
    supplier_name: str,
    our_ref: str,
    sku_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> dict:
    if supplier_id is None:
        supplier_id = await _create_supplier(client, supplier_name)
    if sku_id is None:
        sku = await _create_sku(
            client,
            our_ref,
            f"{our_ref}-BAR",
            f"{our_ref} name",
            f"{our_ref} design",
            f"{our_ref} fabric",
        )
        sku_id = sku["id"]
    else:
        sku = {"id": sku_id}
    po = await client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "factory_unit_amount": "40.00"}],
        },
    )
    assert po.status_code == 201
    return {"po": po.json(), "sku": sku, "supplier_id": supplier_id}


async def _complete_po(
    client: AsyncClient,
    *,
    supplier_name: str,
    our_ref: str,
    sku_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
) -> dict:
    created = await _create_open_po(
        client,
        supplier_name=supplier_name,
        our_ref=our_ref,
        sku_id=sku_id,
        supplier_id=supplier_id,
    )
    po_id = created["po"]["id"]
    water = await client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert water.status_code == 200
    await _land(client, po_id)
    received = await _receive(client, po_id)
    created["po"] = received
    return created


async def _set_clock(
    async_db: AsyncSession,
    po_id: str,
    *,
    ordered_at: datetime.datetime,
    received_at: datetime.datetime,
    on_water_at: Optional[datetime.datetime] = None,
    landed_at: Optional[datetime.datetime] = None,
) -> None:
    values = {
        "ordered_at": ordered_at,
        "received_at": received_at,
        "on_water_at": on_water_at,
        "landed_at": landed_at,
    }
    await async_db.execute(
        sa.update(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(po_id)).values(**values)
    )
    await async_db.flush()


async def test_create_on_water_land_receive_stores_four_timestamps(
    owner_client: AsyncClient,
) -> None:
    created = await _complete_po(
        owner_client, supplier_name="Lead Stamp Supplier", our_ref="LEAD-STAMP"
    )
    body = created["po"]
    assert body["ordered_at"] is not None
    assert body["on_water_at"] is not None
    assert body["landed_at"] is not None
    assert body["received_at"] is not None
    assert _as_naive_utc(_parse_dt(body["ordered_at"])) == _as_naive_utc(
        _parse_dt(body["created_at"])
    )


async def test_first_write_wins_second_receive_409(owner_client: AsyncClient) -> None:
    created = await _create_open_po(
        owner_client, supplier_name="Lead First Write", our_ref="LEAD-FIRST"
    )
    po_id = created["po"]["id"]
    first_water = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert first_water.status_code == 200
    stamped_water = first_water.json()["on_water_at"]
    second_water = await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    assert second_water.status_code == 409
    still_water = await owner_client.get(f"/api/v1/purchase-orders/{po_id}")
    assert still_water.json()["on_water_at"] == stamped_water

    await _land(owner_client, po_id)
    received = await _receive(owner_client, po_id)
    stamped_received = received["received_at"]
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    again = await owner_client.post(
        "/api/v1/receive",
        json={"purchase_order_id": po_id, "location_id": location_id},
    )
    assert again.status_code == 409
    after = await owner_client.get(f"/api/v1/purchase-orders/{po_id}")
    assert after.json()["received_at"] == stamped_received


async def test_median_10_20_100_via_reports(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    first = await _complete_po(
        owner_client, supplier_name="Lead Median Supplier", our_ref="LEAD-MED-A"
    )
    supplier_id = first["supplier_id"]
    sku_id = first["sku"]["id"]
    second = await _complete_po(
        owner_client,
        supplier_name="Lead Median Supplier",
        our_ref="LEAD-MED-B",
        sku_id=sku_id,
        supplier_id=supplier_id,
    )
    third = await _complete_po(
        owner_client,
        supplier_name="Lead Median Supplier",
        our_ref="LEAD-MED-C",
        sku_id=sku_id,
        supplier_id=supplier_id,
    )
    clocks = (
        (first["po"]["id"], 100, _utc(2026, 1, 10)),
        (second["po"]["id"], 20, _utc(2026, 2, 10)),
        (third["po"]["id"], 10, _utc(2026, 3, 10)),
    )
    for po_id, days, received_at in clocks:
        await _set_clock(
            async_db,
            po_id,
            ordered_at=received_at - datetime.timedelta(days=days),
            received_at=received_at,
            on_water_at=received_at - datetime.timedelta(days=days - 2),
        )

    resp = await owner_client.get("/api/v1/reports/supplier-lead-times")
    assert resp.status_code == 200
    line = next(row for row in resp.json()["lines"] if row["supplier_id"] == supplier_id)
    assert line["n"] == 3
    assert line["median_days"] == 20
    assert line["median_last_3_days"] == 20
    assert line["median_water_days"] == 18
    assert line["p90_days"] is not None

    sku_resp = await owner_client.get("/api/v1/reports/sku-lead-times")
    assert sku_resp.status_code == 200
    sku_line = next(row for row in sku_resp.json()["lines"] if row["sku_id"] == sku_id)
    assert sku_line["n"] == 3
    assert sku_line["median_days"] == 20


async def test_median_last_3_uses_newest_three(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    first = await _complete_po(
        owner_client, supplier_name="Lead Last3 Supplier", our_ref="LEAD-L3-A"
    )
    supplier_id = first["supplier_id"]
    sku_id = first["sku"]["id"]
    extras = [first]
    for suffix in ("B", "C", "D"):
        extras.append(
            await _complete_po(
                owner_client,
                supplier_name="Lead Last3 Supplier",
                our_ref=f"LEAD-L3-{suffix}",
                sku_id=sku_id,
                supplier_id=supplier_id,
            )
        )
    clocks = (
        (extras[0]["po"]["id"], 100, _utc(2026, 1, 10)),
        (extras[1]["po"]["id"], 40, _utc(2026, 2, 10)),
        (extras[2]["po"]["id"], 20, _utc(2026, 3, 10)),
        (extras[3]["po"]["id"], 10, _utc(2026, 4, 10)),
    )
    for po_id, days, received_at in clocks:
        await _set_clock(
            async_db,
            po_id,
            ordered_at=received_at - datetime.timedelta(days=days),
            received_at=received_at,
        )

    resp = await owner_client.get("/api/v1/reports/supplier-lead-times")
    line = next(row for row in resp.json()["lines"] if row["supplier_id"] == supplier_id)
    assert line["n"] == 4
    assert line["median_days"] == 30
    assert line["median_last_3_days"] == 20
    assert line["median_water_days"] is None


async def test_incomplete_and_missing_received_at_omitted(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    open_po = await _create_open_po(
        owner_client, supplier_name="Lead Incomplete Open", our_ref="LEAD-OPEN"
    )
    water = await _create_open_po(
        owner_client, supplier_name="Lead Incomplete Water", our_ref="LEAD-WATER"
    )
    await owner_client.post(f"/api/v1/purchase-orders/{water['po']['id']}/on-water")

    historic = await _complete_po(
        owner_client, supplier_name="Lead Incomplete Historic", our_ref="LEAD-HIST"
    )
    await async_db.execute(
        sa.update(PurchaseOrder)
        .where(PurchaseOrder.id == uuid.UUID(historic["po"]["id"]))
        .values(received_at=None)
    )
    await async_db.flush()

    resp = await owner_client.get("/api/v1/reports/supplier-lead-times")
    assert resp.status_code == 200
    supplier_ids = {row["supplier_id"] for row in resp.json()["lines"]}
    assert open_po["supplier_id"] not in supplier_ids
    assert water["supplier_id"] not in supplier_ids
    assert historic["supplier_id"] not in supplier_ids

    sku_resp = await owner_client.get("/api/v1/reports/sku-lead-times")
    sku_ids = {row["sku_id"] for row in sku_resp.json()["lines"]}
    assert open_po["sku"]["id"] not in sku_ids
    assert historic["sku"]["id"] not in sku_ids


async def test_receive_does_not_write_sku_lead_time_days(owner_client: AsyncClient) -> None:
    sku = await _create_sku(
        owner_client,
        "LEAD-MANUAL",
        "LEAD-MANUAL-BAR",
        "Manual lead sofa",
        "Manual design",
        "Manual fabric",
    )
    patch = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"lead_time_days": 21})
    assert patch.status_code == 200
    await _complete_po(
        owner_client,
        supplier_name="Lead Manual Supplier",
        our_ref="LEAD-MANUAL-PO",
        sku_id=sku["id"],
    )
    got = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert got.status_code == 200
    assert got.json()["lead_time_days"] == 21

    report = await owner_client.get("/api/v1/reports/sku-lead-times")
    line = next(row for row in report.json()["lines"] if row["sku_id"] == sku["id"])
    assert line["manual_lead_time_days"] == 21


async def test_warehouse_can_read_lead_time_reports(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _complete_po(owner_client, supplier_name="Lead Warehouse Supplier", our_ref="LEAD-WH")
    async_client.cookies.clear()
    login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "warehouse@example.com",
            "password": settings.seed_warehouse_password,
        },
    )
    assert login.status_code == 200
    json_resp = await async_client.get("/api/v1/reports/supplier-lead-times")
    assert json_resp.status_code == 200
    csv_resp = await async_client.get("/api/v1/reports/sku-lead-times/csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert b"manual_lead_time_days" in csv_resp.content
    await _relogin_owner(owner_client)


async def test_receive_leaves_sku_lead_time_days_null_in_db(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    created = await _complete_po(
        owner_client, supplier_name="Lead Null Manual", our_ref="LEAD-NULL-MAN"
    )
    sku_id = uuid.UUID(created["sku"]["id"])
    row = (
        await async_db.execute(sa.select(Sku.lead_time_days).where(Sku.id == sku_id))
    ).scalar_one()
    assert row is None
