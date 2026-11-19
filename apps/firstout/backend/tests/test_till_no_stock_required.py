"""Opt-in service lines have their own till and returns stock behavior."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.services.chart_of_accounts import CODE_COGS, CODE_INVENTORY
from tests.test_purchase_orders import _location_id_by_name
from tests.test_sku_bom import _sku
from tests.test_stock_returns import _return_payload
from tests.test_till import _inventory_on_hand


async def _inventory_accounts(client: AsyncClient) -> tuple[Decimal, Decimal]:
    result = await client.get("/api/v1/accounts")
    assert result.status_code == 200, result.text
    balances = {account["code"]: Decimal(account["balance_zar"]) for account in result.json()}
    return balances[CODE_INVENTORY], balances[CODE_COGS]


async def test_non_stock_service_requires_opt_in_and_price_and_credits_without_restock(
    owner_client: AsyncClient,
) -> None:
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    service = await _sku(owner_client, "TILL-DELIVERY-SERVICE")
    sku_id = service["id"]
    sku_url = f"/api/v1/skus/{sku_id}"
    checkout = {
        "location_id": showroom,
        "lines": [{"sku_id": sku_id, "qty": 2}],
        "tender": "cash",
    }
    assert service["till_no_stock_required"] is False
    opted_in = await owner_client.patch(sku_url, json={"till_no_stock_required": True})
    assert opted_in.status_code == 200, opted_in.text
    assert opted_in.json()["till_no_stock_required"] is True
    unpriced = await owner_client.post("/api/v1/till/sales", json=checkout)
    assert unpriced.status_code == 400
    assert "no retail price" in unpriced.json()["detail"]

    priced = await owner_client.patch(
        sku_url, json={"retail_ex_vat": "100.00", "till_no_stock_required": False}
    )
    assert priced.status_code == 200, priced.text
    no_stock = await owner_client.post("/api/v1/till/sales", json=checkout)
    assert no_stock.status_code == 409
    assert "Insufficient on-hand quantity" in no_stock.json()["detail"]

    disabled = await owner_client.patch(
        sku_url, json={"till_no_stock_required": True, "is_sellable": False}
    )
    assert disabled.status_code == 200, disabled.text
    unsellable = await owner_client.post("/api/v1/till/sales", json=checkout)
    assert unsellable.status_code == 400
    assert "not available for new sales" in unsellable.json()["detail"]
    enabled = await owner_client.patch(sku_url, json={"is_sellable": True})
    assert enabled.status_code == 200, enabled.text

    before = await _inventory_accounts(owner_client)
    response = await owner_client.post("/api/v1/till/sales", json=checkout)
    assert response.status_code == 201, response.text
    sale = response.json()
    assert Decimal(sale["total_inc_vat"]) == Decimal("230.00")
    assert sale["lines"][0]["till_no_stock_required"] is True
    assert await _inventory_accounts(owner_client) == before

    opted_out = await owner_client.patch(sku_url, json={"till_no_stock_required": False})
    assert opted_out.status_code == 200, opted_out.text
    invoice = await owner_client.get(f"/api/v1/invoices/{sale['invoice_id']}")
    assert invoice.status_code == 200, invoice.text
    assert invoice.json()["lines"][0]["till_no_stock_required"] is True

    payload = _return_payload(sale["invoice_id"], showroom, sale["lines"][0]["id"], "restock")
    response = await owner_client.post("/api/v1/returns", json=payload)
    assert response.status_code == 400
    assert "Non-stock till services cannot be restocked" in response.json()["detail"]
    payload["disposition"] = "write_off"
    response = await owner_client.post("/api/v1/returns", json=payload)
    assert response.status_code == 201, response.text
    done = await owner_client.post(f"/api/v1/returns/{response.json()['id']}/complete")
    assert done.status_code == 200, done.text
    assert done.json()["credit_note_id"] is not None
    assert await _inventory_accounts(owner_client) == before
    inventory = await owner_client.get("/api/v1/inventory")
    assert inventory.status_code == 200, inventory.text
    assert all(line["sku_id"] != sku_id for line in inventory.json())


async def test_mixed_sale_and_restock_only_move_the_items_that_used_stock(
    owner_client: AsyncClient,
) -> None:
    showroom = await _location_id_by_name(owner_client, "Bedfordview")
    furniture = await _sku(
        owner_client,
        "TILL-SERVICE-CHAIR",
        retail_ex_vat="500.00",
        opening_location_id=showroom,
        opening_qty=2,
        opening_cost="110.00",
    )
    service = await _sku(
        owner_client,
        "TILL-INSTALLATION-SERVICE",
        retail_ex_vat="100.00",
        opening_location_id=showroom,
        opening_qty=1,
        opening_cost="30.00",
    )
    opted_in = await owner_client.patch(
        f"/api/v1/skus/{service['id']}", json={"till_no_stock_required": True}
    )
    assert opted_in.status_code == 200, opted_in.text

    inventory_before, cogs_before = await _inventory_accounts(owner_client)
    response = await owner_client.post(
        "/api/v1/till/sales",
        json={
            "location_id": showroom,
            "lines": [{"sku_id": sku["id"], "qty": 1} for sku in (furniture, service)],
            "tender": "cash",
        },
    )
    assert response.status_code == 201, response.text
    sale = response.json()
    assert [line["till_no_stock_required"] for line in sale["lines"]] == [False, True]
    assert Decimal(sale["total_inc_vat"]) == Decimal("690.00")
    assert await _inventory_on_hand(owner_client, furniture["id"], showroom) == 1
    assert await _inventory_on_hand(owner_client, service["id"], showroom) == 1
    assert await _inventory_accounts(owner_client) == (
        inventory_before - Decimal("110.00"),
        cogs_before + Decimal("110.00"),
    )

    # A subsequent catalogue change does not turn a stocked sale into a service.
    response = await owner_client.patch(
        f"/api/v1/skus/{furniture['id']}", json={"till_no_stock_required": True}
    )
    assert response.status_code == 200, response.text

    payload = _return_payload(sale["invoice_id"], showroom, sale["lines"][0]["id"], "restock")
    payload["lines"].append({"invoice_line_id": sale["lines"][1]["id"], "qty": 1})
    created = await owner_client.post("/api/v1/returns", json=payload)
    assert created.status_code == 201, created.text
    done = await owner_client.post(f"/api/v1/returns/{created.json()['id']}/complete")
    assert done.status_code == 200, done.text
    assert await _inventory_on_hand(owner_client, furniture["id"], showroom) == 2
    assert await _inventory_on_hand(owner_client, service["id"], showroom) == 1
    assert await _inventory_accounts(owner_client) == (inventory_before, cogs_before)
    credit = await owner_client.get(f"/api/v1/credit-notes/{done.json()['credit_note_id']}")
    assert credit.status_code == 200, credit.text
    assert Decimal(credit.json()["total_inc_vat"]) == Decimal("690.00")


async def test_non_stock_service_cannot_be_made_a_kit(owner_client: AsyncClient) -> None:
    parent_response = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "SERVICE-KIT",
            "name": "Service kit",
            "design": "Service kit",
            "fabric": "-",
            "till_no_stock_required": True,
        },
    )
    assert parent_response.status_code == 201, parent_response.text
    parent = parent_response.json()
    assert parent["till_no_stock_required"] is True
    component = await _sku(owner_client, "SERVICE-KIT-COMPONENT")
    sku_url = f"/api/v1/skus/{parent['id']}"
    recipe = {"lines": [{"component_sku_id": component["id"], "qty": 1}]}
    assert (await owner_client.put(f"{sku_url}/bom", json=recipe)).status_code == 409
    assert (
        await owner_client.patch(sku_url, json={"till_no_stock_required": False})
    ).status_code == 200
    assert (await owner_client.put(f"{sku_url}/bom", json=recipe)).status_code == 200
    assert (
        await owner_client.patch(sku_url, json={"till_no_stock_required": True})
    ).status_code == 409
