"""V2-S15 stock and sales report tests."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock
from tests.test_purchase_orders import (
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


async def _kramerville_id(client: AsyncClient) -> str:
    return await _location_id_by_name(client, "Kramerville")


async def _set_retail_price(client: AsyncClient, sku_id: str, retail_ex: str) -> None:
    resp = await client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": retail_ex},
    )
    assert resp.status_code == 200


async def _transfer_to_bedfordview(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    sku_id: str,
    qty: int,
) -> str:
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-po@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200
    await _relogin_owner(owner_client)
    transfer = await complete_location_transfer(
        async_client,
        kramerville_id,
        bedford_id,
        sku_id,
        qty,
    )
    assert transfer["status"] == "received"
    return bedford_id


async def test_stock_valuation_opening_qty_times_cost(
    owner_client: AsyncClient,
) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "RPT-SV-001",
            "our_barcode": "RPT-SV-001-BAR",
            "name": "Report valuation sofa",
            "design": "Report valuation design",
            "fabric": "Report valuation fabric",
            "opening_location_id": location_id,
            "opening_qty": 4,
            "opening_unit_cost_zar": "250.00",
        },
    )
    assert create_resp.status_code == 201
    sku_id = create_resp.json()["id"]

    resp = await owner_client.get("/api/v1/reports/stock-valuation")
    assert resp.status_code == 200
    body = resp.json()
    line = next(
        row
        for row in body["lines"]
        if row["sku_id"] == sku_id and row["location_id"] == location_id
    )
    assert line["on_hand"] == 4
    assert line["unit_cost_zar"] == "250.0000"
    assert line["value_zar"] == "1000.00"
    assert body["total_value_zar"] == "1000.00"


async def test_aged_stock_fresh_stock_in_zero_ninety_bucket(
    owner_client: AsyncClient,
) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "RPT-AGED-001",
            "our_barcode": "RPT-AGED-001-BAR",
            "name": "Fresh aged stock chair",
            "design": "Fresh aged design",
            "fabric": "Fresh aged fabric",
            "opening_location_id": location_id,
            "opening_qty": 3,
            "opening_unit_cost_zar": "100.00",
        },
    )
    assert create_resp.status_code == 201

    resp = await owner_client.get("/api/v1/reports/aged-stock")
    assert resp.status_code == 200
    body = resp.json()
    bucket = next(b for b in body["buckets"] if b["bucket"] == "0-90")
    assert bucket["qty"] >= 3
    assert Decimal(bucket["value_zar"]) >= Decimal("300.00")
    assert any(line["our_ref"] == "RPT-AGED-001" for line in bucket["lines"])


async def test_aged_stock_one_eighty_plus_after_backdated_update(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    location_id = await _kramerville_id(owner_client)
    create_resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "RPT-AGED-OLD",
            "our_barcode": "RPT-AGED-OLD-BAR",
            "name": "Old aged stock table",
            "design": "Old aged design",
            "fabric": "Old aged fabric",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "500.00",
        },
    )
    assert create_resp.status_code == 201
    sku_id = uuid.UUID(create_resp.json()["id"])

    stale = datetime.datetime.utcnow() - datetime.timedelta(days=200)
    await async_db.execute(
        sa.update(LocationStock)
        .where(
            LocationStock.sku_id == sku_id,
            LocationStock.location_id == uuid.UUID(location_id),
        )
        .values(updated_at=stale)
    )
    await async_db.flush()

    resp = await owner_client.get("/api/v1/reports/aged-stock")
    assert resp.status_code == 200
    bucket = next(b for b in resp.json()["buckets"] if b["bucket"] == "180+")
    assert any(line["our_ref"] == "RPT-AGED-OLD" for line in bucket["lines"])


async def test_sales_by_sku_till_sale_in_range(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="RPT-SKU-SALE",
    )
    sku_id = data["sku"]["id"]
    await _set_retail_price(owner_client, sku_id, "800.00")
    bedford_id = await _transfer_to_bedfordview(async_client, owner_client, sku_id, 1)

    till = await _create_till(async_client, owner_client)
    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    issue_date = sale.json()["issue_date"]

    in_range = await owner_client.get(
        "/api/v1/reports/sales-by-sku",
        params={"from": issue_date, "to": issue_date},
    )
    assert in_range.status_code == 200
    body = in_range.json()
    line = next(row for row in body["lines"] if row["our_ref"] == "RPT-SKU-SALE")
    assert line["qty"] == 1
    assert line["ex_vat_zar"] == "800.00"

    out_of_range = await owner_client.get(
        "/api/v1/reports/sales-by-sku",
        params={"from": "2020-01-01", "to": "2020-01-31"},
    )
    assert out_of_range.status_code == 200
    assert all(row["our_ref"] != "RPT-SKU-SALE" for row in out_of_range.json()["lines"])


async def test_sales_vat_15_percent_on_thousand_ex(owner_client: AsyncClient) -> None:
    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Sales VAT Customer"},
    )
    assert customer_resp.status_code == 201
    invoice_resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_resp.json()["id"],
            "issue_date": "2026-09-10",
            "lines": [{"description": "Desk", "qty": 1, "unit_ex_vat": "1000.00"}],
        },
    )
    assert invoice_resp.status_code == 201

    resp = await owner_client.get(
        "/api/v1/reports/sales-vat",
        params={"from": "2026-09-10", "to": "2026-09-10"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["invoice_count"] == 1
    assert body["subtotal_ex_vat"] == "1000.00"
    assert body["vat_amount"] == "150.00"
    assert body["total_inc_vat"] == "1150.00"


async def test_unauthenticated_stock_valuation_returns_401(
    async_client: AsyncClient,
) -> None:
    resp = await async_client.get("/api/v1/reports/stock-valuation")
    assert resp.status_code == 401


async def test_stock_valuation_csv_content_type(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/reports/stock-valuation/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"].lower()
    assert b"location_name" in resp.content


async def test_aged_stock_csv_content_type(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/reports/aged-stock/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"].lower()


async def test_sales_by_sku_csv_content_type(owner_client: AsyncClient) -> None:
    resp = await owner_client.get(
        "/api/v1/reports/sales-by-sku/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"].lower()


async def test_sales_vat_csv_content_type(owner_client: AsyncClient) -> None:
    resp = await owner_client.get(
        "/api/v1/reports/sales-vat/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"].lower()
