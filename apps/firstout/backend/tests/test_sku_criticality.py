"""F8 SKU ABC / Pareto criticality report."""

from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.abc import AbcSkuInput, build_abc_report
from tests.test_purchase_orders import (
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


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


def test_abc_three_way_split_50_30_20() -> None:
    rows = [
        AbcSkuInput(uuid.uuid4(), "A", "Alpha", "Seating", 1, Decimal("50")),
        AbcSkuInput(uuid.uuid4(), "B", "Bravo", "Tables", 1, Decimal("30")),
        AbcSkuInput(uuid.uuid4(), "C", "Charlie", None, 1, Decimal("20")),
    ]
    report = build_abc_report(rows)

    assert report.top_sku_share_pct == Decimal("50.00")
    assert report.sku_count_for_50pct == 1
    assert report.sku_count_for_80pct == 2

    by_ref = {line.our_ref: line for line in report.lines}
    assert by_ref["A"].share_pct == Decimal("50.00")
    assert by_ref["B"].share_pct == Decimal("30.00")
    assert by_ref["C"].share_pct == Decimal("20.00")
    assert by_ref["A"].cumulative_pct == Decimal("50.00")
    assert by_ref["B"].cumulative_pct == Decimal("80.00")
    assert by_ref["C"].cumulative_pct == Decimal("100.00")
    assert by_ref["A"].abc_class == "A"
    assert by_ref["B"].abc_class == "A"
    assert by_ref["C"].abc_class == "C"
    assert by_ref["A"].hits_50pct_band is True
    assert by_ref["B"].hits_50pct_band is False
    assert by_ref["C"].hits_50pct_band is False
    assert by_ref["A"].is_a is True
    assert by_ref["B"].is_a is True
    assert by_ref["C"].is_a is False

    categories = {line.category: line for line in report.categories}
    assert categories["Seating"].share_pct == Decimal("50.00")
    assert categories["Tables"].share_pct == Decimal("30.00")
    assert categories["Uncategorised"].share_pct == Decimal("20.00")


async def test_sku_criticality_till_sale_ex_vat(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=1,
        location_name="Kramerville",
        our_ref="RPT-ABC-SALE",
    )
    sku_id = data["sku"]["id"]
    patch = await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "1000.00", "category": "Seating"},
    )
    assert patch.status_code == 200
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

    resp = await owner_client.get(
        "/api/v1/reports/sku-criticality",
        params={"from": issue_date, "to": issue_date},
    )
    assert resp.status_code == 200
    body = resp.json()
    line = next(row for row in body["lines"] if row["our_ref"] == "RPT-ABC-SALE")
    assert line["qty"] == 1
    assert line["value_zar"] == "1000.00"
    assert line["category"] == "Seating"
    assert line["abc_class"] in {"A", "B", "C"}
    assert line["is_a"] == (line["abc_class"] == "A")
    assert isinstance(line["hits_50pct_band"], bool)
    assert body["sku_count_for_50pct"] >= 1
    assert body["sku_count_for_80pct"] >= 1
    assert Decimal(body["top_sku_share_pct"]) > 0


async def test_sales_by_sku_csv_header_unchanged(owner_client: AsyncClient) -> None:
    resp = await owner_client.get(
        "/api/v1/reports/sales-by-sku/csv",
        params={"from": "2026-09-01", "to": "2026-09-30"},
    )
    assert resp.status_code == 200
    rows = list(csv.reader(io.StringIO(resp.text)))
    assert rows[1] == ["sku_id", "our_ref", "name", "qty", "ex_vat_zar", "inc_vat_zar"]


async def test_sku_criticality_does_not_write_lead_time_days(
    owner_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    from app.models.sku import Sku

    sku_id = uuid.uuid4()
    await async_db.execute(
        sa.insert(Sku).values(
            id=sku_id,
            our_ref="RPT-ABC-LTD",
            our_barcode="RPT-ABC-LTD-BAR",
            name="Lead time sentinel",
            design="ABC",
            fabric="-",
            lead_time_days=14,
        )
    )
    await async_db.flush()

    resp = await owner_client.get("/api/v1/reports/sku-criticality")
    assert resp.status_code == 200

    row = await async_db.get(Sku, sku_id)
    assert row is not None
    assert row.lead_time_days == 14
