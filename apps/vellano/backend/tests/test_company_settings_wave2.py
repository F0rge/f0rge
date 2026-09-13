"""Settings caps and wholesale pricing."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.test_purchase_orders import (
    MINIMAL_PDF,
    _create_buyer,
    _create_sku,
    _create_supplier,
    _create_till,
    _location_id_by_name,
    _login_as,
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


async def test_po_threshold_converts_factory_currency_to_zar(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await owner_client.patch(
        "/api/v1/settings",
        json={"po_approval_threshold_zar": "1000.00"},
    )
    usd = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "USD Cap Supplier", "default_currency": "USD"},
    )
    assert usd.status_code == 201
    usd_id = usd.json()["id"]
    sku_usd = await _create_sku(
        owner_client,
        "CAP-USD",
        "CAP-USD-BAR",
        "Cap USD SKU",
        "CapUSD",
        "FabricUSD",
    )
    zar = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "ZAR Cap Supplier", "default_currency": "ZAR"},
    )
    assert zar.status_code == 201
    zar_id = zar.json()["id"]
    sku_zar = await _create_sku(
        owner_client,
        "CAP-ZAR",
        "CAP-ZAR-BAR",
        "Cap ZAR SKU",
        "CapZAR",
        "FabricZAR",
    )
    buyer = await _create_buyer(async_client, owner_client)

    # 80 USD looks under 1000 if compared raw; no prior FX so it must not slip through.
    blocked_raw = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": usd_id,
            "lines": [{"sku_id": sku_usd["id"], "qty": 1, "factory_unit_amount": "80.00"}],
        },
    )
    assert blocked_raw.status_code == 409

    allowed_zar = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": zar_id,
            "lines": [{"sku_id": sku_zar["id"], "qty": 1, "factory_unit_amount": "80.00"}],
        },
    )
    assert allowed_zar.status_code == 201

    await _relogin_owner(owner_client)
    seed = await owner_client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": usd_id,
            "lines": [{"sku_id": sku_usd["id"], "qty": 1, "factory_unit_amount": "10.00"}],
        },
    )
    assert seed.status_code == 201
    po_id = seed.json()["id"]
    await owner_client.post(f"/api/v1/purchase-orders/{po_id}/on-water")
    land = await owner_client.post(
        f"/api/v1/purchase-orders/{po_id}/land",
        data={
            "fx_to_zar": "18.00",
            "factory_invoice_number": "FAC-CAP",
            "factory_amount": "10.00",
            "factory_currency": "USD",
            "freight_invoice_number": "FRE-CAP",
            "freight_amount": "1.00",
            "freight_currency": "ZAR",
            "clearance_invoice_number": "CLR-CAP",
            "clearance_amount": "1.00",
            "clearance_currency": "ZAR",
        },
        files={
            "factory_file": ("f.pdf", MINIMAL_PDF, "application/pdf"),
            "freight_file": ("fr.pdf", MINIMAL_PDF, "application/pdf"),
            "clearance_file": ("c.pdf", MINIMAL_PDF, "application/pdf"),
        },
    )
    assert land.status_code == 200

    buyer = await _login_as(async_client, "buyer-po@example.com", "buyer-password")
    # 50 USD * 18 = 900 ZAR, under 1000.
    under = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": usd_id,
            "lines": [{"sku_id": sku_usd["id"], "qty": 1, "factory_unit_amount": "50.00"}],
        },
    )
    assert under.status_code == 201
    # 80 USD * 18 = 1440 ZAR, over 1000.
    over = await buyer.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": usd_id,
            "lines": [{"sku_id": sku_usd["id"], "qty": 1, "factory_unit_amount": "80.00"}],
        },
    )
    assert over.status_code == 409


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
