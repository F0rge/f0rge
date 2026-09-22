"""Named price lists and customer price resolution."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient

from tests.test_purchase_orders import (
    _create_buyer,
    _create_sku,
    _create_till,
    _location_id_by_name,
    _relogin_owner,
)
from tests.test_transfers import _receive_qty_at_location, complete_location_transfer


async def _stock_sku_at_bedford(
    async_client: AsyncClient,
    owner_client: AsyncClient,
    our_ref: str,
    qty: int = 3,
) -> tuple[str, str]:
    data = await _receive_qty_at_location(
        async_client,
        owner_client,
        qty=qty,
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
        qty,
    )
    return sku_id, bedford_id


async def test_create_list_upsert_item_duplicate_name_409(
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Decorator"},
    )
    assert created.status_code == 201
    price_list_id = created.json()["id"]

    sku = await _create_sku(
        owner_client,
        "PL-SKU-1",
        "PL-SKU-1-BAR",
        "Price list SKU",
        "PL",
        "Fabric",
    )
    item = await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku["id"], "unit_ex_vat": "900.00"},
    )
    assert item.status_code == 200
    assert item.json()["items"][0]["unit_ex_vat"] == "900.00"
    assert item.json()["items"][0]["our_ref"] == "PL-SKU-1"

    dup = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Decorator"},
    )
    assert dup.status_code == 409


async def test_customer_price_list_id_unknown_404_valid_get(
    owner_client: AsyncClient,
) -> None:
    created = await owner_client.post(
        "/api/v1/customers",
        json={"name": "List Customer", "price_list_id": str(uuid4())},
    )
    assert created.status_code == 404

    price_list = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Trade list"},
    )
    assert price_list.status_code == 201
    price_list_id = price_list.json()["id"]

    customer = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Assigned Customer",
            "customer_type": "trade",
            "price_list_id": price_list_id,
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    fetched = await owner_client.get(f"/api/v1/customers/{customer_id}")
    assert fetched.status_code == 200
    assert fetched.json()["price_list_id"] == price_list_id


async def test_till_resolve_list_wholesale_retail_matrix(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, bedford_id = await _stock_sku_at_bedford(async_client, owner_client, "PL-TILL")

    price_list = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Till decorator"},
    )
    assert price_list.status_code == 201
    price_list_id = price_list.json()["id"]
    await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "900.00"},
    )

    trade_a = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Trade On List",
            "customer_type": "trade",
            "price_list_id": price_list_id,
        },
    )
    assert trade_a.status_code == 201

    trade_b = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Trade No List", "customer_type": "trade"},
    )
    assert trade_b.status_code == 201

    retail = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Retail Walk", "customer_type": "retail"},
    )
    assert retail.status_code == 201

    till = await _create_till(async_client, owner_client)

    sale_a = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": trade_a.json()["id"],
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale_a.status_code == 201
    assert Decimal(sale_a.json()["lines"][0]["unit_ex_vat"]) == Decimal("900.00")

    sale_b = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": trade_b.json()["id"],
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale_b.status_code == 201
    assert Decimal(sale_b.json()["lines"][0]["unit_ex_vat"]) == Decimal("800.00")

    sale_retail = await till.post(
        "/api/v1/till/sales",
        json={
            "location_id": bedford_id,
            "customer_id": retail.json()["id"],
            "lines": [{"sku_id": sku_id, "qty": 1, "discount_percent": "0"}],
            "tender": "cash",
        },
    )
    assert sale_retail.status_code == 201
    assert Decimal(sale_retail.json()["lines"][0]["unit_ex_vat"]) == Decimal("1000.00")


async def test_books_invoice_resolves_price_list(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, _bedford_id = await _stock_sku_at_bedford(async_client, owner_client, "PL-BOOKS")

    price_list = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Books list"},
    )
    assert price_list.status_code == 201
    price_list_id = price_list.json()["id"]
    await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "900.00"},
    )

    customer = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Books trade list",
            "customer_type": "trade",
            "price_list_id": price_list_id,
        },
    )
    assert customer.status_code == 201

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [{"description": "Listed", "qty": 1, "sku_id": sku_id}],
        },
    )
    assert invoice.status_code == 201
    assert Decimal(invoice.json()["lines"][0]["unit_ex_vat"]) == Decimal("900.00")


async def test_books_invoice_explicit_unit_wins_over_list(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku_id, _bedford_id = await _stock_sku_at_bedford(async_client, owner_client, "PL-EXPLICIT")

    price_list = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Explicit override list"},
    )
    assert price_list.status_code == 201
    price_list_id = price_list.json()["id"]
    await owner_client.put(
        f"/api/v1/price-lists/{price_list_id}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "900.00"},
    )

    customer = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Explicit buyer",
            "customer_type": "trade",
            "price_list_id": price_list_id,
        },
    )
    assert customer.status_code == 201

    invoice = await owner_client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer.json()["id"],
            "issue_date": "2026-09-01",
            "lines": [
                {
                    "description": "Manual price",
                    "qty": 1,
                    "sku_id": sku_id,
                    "unit_ex_vat": "650.00",
                }
            ],
        },
    )
    assert invoice.status_code == 201
    assert Decimal(invoice.json()["lines"][0]["unit_ex_vat"]) == Decimal("650.00")


async def test_buyer_can_post_price_lists_till_cannot(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    buyer = await _create_buyer(async_client, owner_client)
    allowed = await buyer.post(
        "/api/v1/price-lists",
        json={"name": "Buyer list"},
    )
    assert allowed.status_code == 201

    await _relogin_owner(owner_client)
    till = await _create_till(async_client, owner_client)
    blocked = await till.post(
        "/api/v1/price-lists",
        json={"name": "Till list"},
    )
    assert blocked.status_code == 403
