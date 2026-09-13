"""Settings caps and wholesale pricing."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.test_purchase_orders import (
    _create_buyer,
    _create_sku,
    _create_supplier,
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


async def _stock_sku_at_bedford(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
) -> tuple[str, str]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=2,
        location_name="Kramerville",
        our_ref=our_ref,
    )
    sku_id = data["sku"]["id"]
    await owner_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "1000.00", "wholesale_ex_vat": "800.00"},
    )
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    await complete_location_transfer(
        owner_client,
        kramerville_id,
        bedford_id,
        sku_id,
        2,
    )
    return sku_id, bedford_id


async def test_till_discount_cap_409_without_manage(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await owner_client.patch(
        "/api/v1/settings",
        json={"max_till_discount_percent": "10.00"},
    )
    sku_id, bedford_id = await _stock_sku_at_bedford(async_client, owner_client, "CAP-TILL")
    till = await _create_till(async_client, owner_client)

    blocked = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "15"}],
            "tender": "cash",
        },
    )
    assert blocked.status_code == 409

    await _relogin_owner(owner_client)
    allowed = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "15"}],
            "tender": "cash",
        },
    )
    assert allowed.status_code == 201


async def test_po_threshold_409_for_buyer(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await owner_client.patch(
        "/api/v1/settings",
        json={"po_approval_threshold_zar": "100.00"},
    )
    supplier_id = await _create_supplier(owner_client, "Cap Supplier")
    sku = await _create_sku(
        owner_client,
        "CAP-PO",
        "CAP-PO-BAR",
        "Cap PO SKU",
        "Cap",
        "Fabric",
    )
    buyer = await _create_buyer(async_client, owner_client)

    blocked = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "500.00"}],
        },
    )
    assert blocked.status_code == 409

    await _relogin_owner(owner_client)
    allowed = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "lines": [{"sku_id": sku["id"], "qty": 1, "factory_unit_amount": "500.00"}],
        },
    )
    assert allowed.status_code == 201


async def test_books_invoice_uses_wholesale_for_trade_customer(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(
        owner_client,
        "WHOLESALE-BOOKS",
        "WHOLESALE-BOOKS-BAR",
        "Wholesale books SKU",
        "Wholesale",
        "Fabric",
    )
    await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": "1000.00", "wholesale_ex_vat": "700.00"},
    )
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Trade Buyer", "customer_type": "trade"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    resp = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-09-01",
            "lines": [
                {
                    "description": "Trade line",
                    "qty": 1,
                    "sku_id": sku["id"],
                }
            ],
        },
    )
    assert resp.status_code == 201
    line = resp.json()["lines"][0]
    assert Decimal(line["unit_ex_vat"]) == Decimal("700.00")


async def test_till_trade_customer_uses_wholesale(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stock_sku_at_bedford(async_client, owner_client, "WHOLESALE-TILL")
    trade = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Till Trade", "customer_type": "trade"},
    )
    assert trade.status_code == 201
    till = await _create_till(async_client, owner_client)

    sale = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": trade.json()["id"],
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale.status_code == 201
    line = sale.json()["lines"][0]
    assert Decimal(line["unit_ex_vat"]) == Decimal("800.00")
