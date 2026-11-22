from __future__ import annotations

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfReader

from tests.conftest import authenticate_as, create_test_staff
from tests.test_laybys import _layby_payload, _stocked_sku_at_bedford
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

    # Staff see the price-list note; the customer's PDF never names the internal list.
    saved = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer.json()["id"], "lines": [{"sku_id": sku["id"], "qty": 1}]},
    )
    assert saved.status_code == 201, saved.text
    assert "No price in Optional prices" in saved.json()["lines"][0]["price_warning"]
    pdf = await owner_client.get(f"/api/v1/quotes/{saved.json()['id']}/pdf")
    assert pdf.status_code == 200
    text = "".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "PRICE-FALLBACK" in text and "Optional prices" not in text


async def test_layby_prices_from_the_customers_price_list(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    """Laybys follow Sale line pricing: price list, then tier, then Retail (ADR 0001)."""
    sku_id, bedford_id = await _stocked_sku_at_bedford(async_client, owner_client, "LAYBY-LIST")
    await _relogin_owner(owner_client)
    price_list = await owner_client.post("/api/v1/price-lists", json={"name": "Layby trade list"})
    assert price_list.status_code == 201, price_list.text
    item = await owner_client.put(
        f"/api/v1/price-lists/{price_list.json()['id']}/items",
        json={"sku_id": sku_id, "unit_ex_vat": "800.00"},
    )
    assert item.status_code == 200, item.text
    customer = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Layby list account", "price_list_id": price_list.json()["id"]},
    )
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]

    preview = await owner_client.post(
        "/api/v1/laybys/preview",
        json={"customer_id": customer_id, "lines": [{"sku_id": sku_id, "qty": 1}]},
    )
    assert preview.status_code == 200, preview.text
    line = preview.json()["lines"][0]
    assert (line["unit_ex_vat"], line["source"]) == ("800.00", "price_list")
    assert preview.json()["total_inc_vat"] == "920.00"

    created = await owner_client.post(
        "/api/v1/laybys", json=_layby_payload(customer_id, bedford_id, sku_id, deposit="100.00")
    )
    assert created.status_code == 201, created.text
    assert created.json()["lines"][0]["unit_ex_vat"] == "800.00"
    assert created.json()["total_inc_vat"] == preview.json()["total_inc_vat"]


async def test_custom_role_with_till_discount_discounts_a_quote_but_cannot_override(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    """Discount authority is the till.discount permission, never a role slug (ADR 0002)."""
    sku = await _create_sku(
        owner_client, "QUOTE-DESK", "QUOTE-DESK-BAR", "Test product", "Desk", "Linen"
    )
    patched = await owner_client.patch(f"/api/v1/skus/{sku['id']}", json={"retail_ex_vat": "33.33"})
    assert patched.status_code == 200, patched.text
    customer = await owner_client.post("/api/v1/customers", json={"name": "Quote desk account"})
    assert customer.status_code == 201, customer.text
    role = await owner_client.post(
        "/api/v1/roles",
        json={"name": "Quote desk", "permissions": ["sales.quotes", "till.discount"]},
    )
    assert role.status_code == 201, role.text
    await create_test_staff(owner_client, email="quote-desk@example.com", role=role.json()["slug"])
    assert (await authenticate_as(async_client, "quote-desk@example.com")).status_code == 200

    line = {"sku_id": sku["id"], "qty": 3, "discount_percent": "10"}
    quote = await async_client.post(
        "/api/v1/quotes", json={"customer_id": customer.json()["id"], "lines": [line]}
    )
    assert quote.status_code == 201, quote.text
    # Rounded once per line: R33.33 × 3 less 10% is R89.99 (R90.00 when the unit was rounded).
    assert quote.json()["subtotal_ex_vat"] == "89.99"
    assert quote.json()["lines"][0]["unit_ex_vat"] == "33.33"

    preview = await async_client.post(
        "/api/v1/quotes/preview",
        json={
            "customer_id": customer.json()["id"],
            "lines": [{**line, "unit_ex_vat": "30.00"}],
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["lines"][0]["blocked_by"] == "sales.price_override"
    override = await async_client.post(
        "/api/v1/quotes",
        json={"customer_id": customer.json()["id"], "lines": [{**line, "unit_ex_vat": "30.00"}]},
    )
    assert override.status_code == 403
    assert "sales.price_override" in override.json()["detail"]
    await _relogin_owner(owner_client)


async def _quote_preview(client: AsyncClient, customer_id: str, line: dict) -> dict:
    preview = await client.post(
        "/api/v1/quotes/preview", json={"customer_id": customer_id, "lines": [line]}
    )
    assert preview.status_code == 200, preview.text
    return preview.json()["lines"][0]


async def test_cost_warnings_never_follow_an_input_the_caller_may_not_set(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    """A user without stock.cost.view cannot probe average cost through a preview."""
    sku_id, _ = await _stocked_sku_at_bedford(async_client, owner_client, "COST-ORACLE")
    await _relogin_owner(owner_client)
    patched = await owner_client.patch(f"/api/v1/skus/{sku_id}", json={"retail_ex_vat": "50000.00"})
    assert patched.status_code == 200, patched.text
    customer = await owner_client.post("/api/v1/customers", json={"name": "Cost oracle account"})
    customer_id = customer.json()["id"]
    below_cost = {"sku_id": sku_id, "qty": 1, "unit_ex_vat": "1500.00"}
    deep_discount = {"sku_id": sku_id, "qty": 1, "discount_percent": "90"}

    # The owner sees cost: the override and the 90% discount are below it.
    owner_override = await _quote_preview(owner_client, customer_id, below_cost)
    assert "below average cost" in owner_override["suspect_price_warning"]
    owner_discount = await _quote_preview(owner_client, customer_id, deep_discount)
    assert "below average cost" in owner_discount["suspect_price_warning"]

    assert (await authenticate_as(async_client, "warehouse@example.com")).status_code == 200
    refused = await _quote_preview(async_client, customer_id, below_cost)
    assert refused["blocked_by"] == "sales.price_override"
    assert refused["suspect_price_warning"] is None
    assert (refused["unit_ex_vat"], refused["ex_vat"]) == ("50000.00", "50000.00")
    # A discount the warehouse may give is judged on the unit before it, never on cost.
    discounted = await _quote_preview(async_client, customer_id, deep_discount)
    assert (discounted["blocked_by"], discounted["suspect_price_warning"]) == (None, None)
    assert discounted["ex_vat"] == "5000.00"
    await _relogin_owner(owner_client)


async def test_invoice_preview_refuses_a_typed_unit_on_a_product_line(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(
        owner_client, "INV-TYPED", "INV-TYPED-BAR", "Test product", "Typed", "Unit"
    )
    customer = await owner_client.post("/api/v1/customers", json={"name": "Typed unit account"})
    line = {"description": "Typed", "sku_id": sku["id"], "qty": 1, "unit_ex_vat": "1.00"}
    preview = await owner_client.post(
        "/api/v1/invoices/preview",
        json={"customer_id": customer.json()["id"], "lines": [line]},
    )
    assert preview.status_code == 422


async def test_changing_a_quotes_customer_prices_its_lines_afresh(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    """A saved override belongs to the customer it was given to (ADR 0002)."""
    sku = await _create_sku(
        owner_client, "QUOTE-MOVE", "QUOTE-MOVE-BAR", "Test product", "Move", "Velvet"
    )
    patched = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}", json={"retail_ex_vat": "1000.00"}
    )
    assert patched.status_code == 200, patched.text
    customers = []
    for name in ("Quote move A", "Quote move B", "Quote move C"):
        created = await owner_client.post("/api/v1/customers", json={"name": name})
        assert created.status_code == 201, created.text
        customers.append(created.json()["id"])
    line = {"sku_id": sku["id"], "qty": 1}
    quote = await owner_client.post(
        "/api/v1/quotes",
        json={"customer_id": customers[0], "lines": [{**line, "unit_ex_vat": "700.00"}]},
    )
    assert quote.status_code == 201, quote.text
    path = f"/api/v1/quotes/{quote.json()['id']}"

    assert (await authenticate_as(async_client, "till@example.com")).status_code == 200
    moved = await async_client.patch(path, json={"customer_id": customers[1], "lines": [line]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["lines"][0]["unit_ex_vat"] == "1000.00"

    # The owner may override prices anyway, so the saved price moves with the quote.
    await _relogin_owner(owner_client)
    kept = await owner_client.patch(path, json={"lines": [{**line, "unit_ex_vat": "700.00"}]})
    assert kept.status_code == 200, kept.text
    moved_by_owner = await owner_client.patch(
        path, json={"customer_id": customers[2], "lines": [line]}
    )
    assert moved_by_owner.status_code == 200, moved_by_owner.text
    assert moved_by_owner.json()["lines"][0]["unit_ex_vat"] == "700.00"
