from __future__ import annotations

from httpx import AsyncClient

from tests.test_purchase_orders import _create_sku, _location_id_by_name, _relogin_owner
from tests.test_till import _inventory_on_hand
from tests.test_transfers import _receive_qty_at_location


async def test_till_uses_assigned_price_without_repricing_stock_and_rechecks_preview(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    stock = await _receive_qty_at_location(
        async_client, owner_client, qty=3, location_name="Bedfordview", our_ref="PRICE-LIST-ITEM"
    )
    await _relogin_owner(owner_client)
    sku = stock["sku"]
    tiers = {"wholesale_ex_vat": "240.00", "retail_ex_vat": "320.00"}
    assert (await owner_client.patch(f"/api/v1/skus/{sku['id']}", json=tiers)).status_code == 200
    missing = await _create_sku(
        owner_client,
        "PRICE-LIST-MISSING",
        "PRICE-LIST-MISSING-BAR",
        "Test product",
        "Design",
        "Fabric",
    )
    missing_update = await owner_client.patch(f"/api/v1/skus/{missing['id']}", json=tiers)
    assert missing_update.status_code == 200
    price_list = await owner_client.post(
        "/api/v1/price-lists",
        json={"name": "Approved trade prices", "till_require_listed_price": True},
    )
    assert price_list.status_code == 201, price_list.text
    assert price_list.json()["till_require_listed_price"] is True
    item_path = f"/api/v1/price-lists/{price_list.json()['id']}/items"
    customer = await owner_client.post(
        "/api/v1/customers",
        json={
            "name": "Trade test account",
            "price_classification": "Wholesale",
            "price_list_id": price_list.json()["id"],
        },
    )
    assert customer.status_code == 201, customer.text

    request = {
        "customer_id": customer.json()["id"],
        "lines": [{"sku_id": sku["id"], "qty": 2, "discount_percent": 15}],
    }
    preview_path = "/api/v1/till/price-preview"
    bedfordview = await _location_id_by_name(owner_client, "Bedfordview")
    assert (await owner_client.post(preview_path, json=request)).status_code == 409
    assert (
        await owner_client.put(item_path, json={"sku_id": sku["id"], "unit_ex_vat": "270.00"})
    ).status_code == 200
    preview = await owner_client.post(preview_path, json=request)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["price_list_name"] == "Approved trade prices"
    assert body["classification"] == "Wholesale"
    assert body["lines"][0]["source"] == "price_list"
    assert body["lines"][0]["unit_ex_vat"] == "270.00"
    assert await _inventory_on_hand(owner_client, sku["id"], bedfordview) == 3

    mixed_request = {**request, "lines": [*request["lines"], {"sku_id": missing["id"], "qty": 1}]}
    mixed = await owner_client.post(preview_path, json=mixed_request)
    assert mixed.status_code == 409
    assert "PRICE-LIST-MISSING" in mixed.text

    assert (
        await owner_client.put(item_path, json={"sku_id": sku["id"], "unit_ex_vat": "275.49"})
    ).status_code == 200
    sale_request = {**request, "location_id": bedfordview, "tender": "cash"}
    sale_path = "/api/v1/till/sales"
    changed = await owner_client.post(
        sale_path, json={**sale_request, "price_revision": body["price_revision"]}
    )
    assert changed.status_code == 409 and "Prices changed" in changed.text
    assert await _inventory_on_hand(owner_client, sku["id"], bedfordview) == 3

    review = await owner_client.post(preview_path, json=request)
    assert review.status_code == 200, review.text
    current = review.json()
    assert current["subtotal_ex_vat"] == "468.33"
    assert current["vat_amount"] == "70.25"
    assert current["total_inc_vat"] == "538.58"
    posted = await owner_client.post(
        sale_path, json={**sale_request, "price_revision": current["price_revision"]}
    )
    assert posted.status_code == 201, posted.text
    for key in ("subtotal_ex_vat", "vat_amount", "total_inc_vat"):
        assert posted.json()[key] == current[key]
    assert await _inventory_on_hand(owner_client, sku["id"], bedfordview) == 1
    unchanged = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert {key: unchanged.json()[key] for key in tiers} == tiers


async def test_existing_optional_list_still_falls_back_with_preview_warning(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(
        owner_client, "PRICE-FALLBACK", "PRICE-FALLBACK-BAR", "Test product", "Design", "Fabric"
    )
    assert (
        await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"retail_ex_vat": "100.00"})
    ).status_code == 200
    price_list = await owner_client.post("/api/v1/price-lists", json={"name": "Optional prices"})
    assert price_list.status_code == 201
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Optional list account", "price_list_id": price_list.json()["id"]},
    )
    assert customer.status_code == 201
    quote = await owner_client.post(
        "/api/v1/till/price-preview",
        json={"customer_id": customer.json()["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["lines"][0]["source"] == "retail"
    assert "No price in Optional prices" in quote.json()["lines"][0]["price_warning"]
    assert quote.json()["total_inc_vat"] == "115.00"
