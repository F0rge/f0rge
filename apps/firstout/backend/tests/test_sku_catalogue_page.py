"""Catalogue SKU pagination stays backward compatible and carries unit cost."""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from app.config import settings
from tests.test_purchase_orders import _location_id_by_name


async def _login(client: AsyncClient, email: str, password: str) -> None:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200


async def _create(client: AsyncClient, our_ref: str, *, category: str, barcode: str) -> dict:
    response = await client.post(
        "/api/v1/skus",
        json={
            "our_ref": our_ref,
            "our_barcode": barcode,
            "name": f"{our_ref} name",
            "design": f"{our_ref} design",
            "fabric": "Linen",
            "category": category,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_sku_list_without_limit_stays_an_array(owner_client: AsyncClient) -> None:
    await _create(owner_client, "PAGE-A", category="Sofas", barcode="PAGE-A-BAR")
    await _create(owner_client, "PAGE-B", category="Dining", barcode="PAGE-B-BAR")
    listed = await owner_client.get("/api/v1/skus")
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
    refs = {row["our_ref"] for row in listed.json()}
    assert {"PAGE-A", "PAGE-B"} <= refs

    searched = await owner_client.get("/api/v1/skus", params={"q": "PAGE-A-BAR"})
    assert isinstance(searched.json(), list)
    assert [row["our_ref"] for row in searched.json()] == ["PAGE-A"]

    underscored = await owner_client.get("/api/v1/skus", params={"q": "PAGE_A"})
    assert underscored.json() == []


async def test_sku_page_and_unit_costs_share_filters(owner_client: AsyncClient) -> None:
    location_id = await _location_id_by_name(owner_client, "Kramerville")
    created = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "COST-1",
            "our_barcode": "COST-1-BAR",
            "name": "Costed sofa",
            "design": "Costed design",
            "fabric": "Wool",
            "category": "Sofas",
            "opening_location_id": location_id,
            "opening_qty": 2,
            "opening_unit_cost_zar": "10.50",
        },
    )
    assert created.status_code == 201
    await _create(owner_client, "COST-2", category="Dining", barcode="COST-2-BAR")

    page = await owner_client.get(
        "/api/v1/skus",
        params={"limit": 10, "offset": 0, "q": "COST-", "category": "sofas"},
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 1
    assert [row["our_ref"] for row in body["items"]] == ["COST-1"]
    assert "Sofas" in body["categories"]
    assert "Dining" in body["categories"]

    costs = await owner_client.get(
        "/api/v1/skus/unit-costs",
        params={"limit": 10, "q": "COST-", "category": "Sofas"},
    )
    assert costs.status_code == 200
    cost_body = costs.json()
    assert cost_body["total"] == 1
    assert cost_body["items"][0]["sku_id"] == created.json()["id"]
    assert Decimal(cost_body["items"][0]["unit_cost_zar"]) == Decimal("10.50")

    inventory = await owner_client.get("/api/v1/inventory")
    inventory_row = next(row for row in inventory.json() if row["sku_id"] == created.json()["id"])
    assert Decimal(inventory_row["unit_cost_zar"]) == Decimal("10.50")

    too_big = await owner_client.get("/api/v1/skus", params={"limit": 101})
    assert too_big.status_code == 422


async def test_unit_costs_hidden_without_permission(async_client: AsyncClient) -> None:
    await _login(async_client, "owner@example.com", settings.seed_owner_password)
    location_id = await _location_id_by_name(async_client, "Kramerville")
    created = await async_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "HIDDEN-COST",
            "our_barcode": "HIDDEN-COST-BAR",
            "name": "Hidden cost",
            "design": "Hidden design",
            "fabric": "Cotton",
            "category": "Sofas",
            "opening_location_id": location_id,
            "opening_qty": 1,
            "opening_unit_cost_zar": "4.00",
        },
    )
    assert created.status_code == 201
    await _login(async_client, "warehouse@example.com", settings.seed_warehouse_password)
    costs = await async_client.get("/api/v1/skus/unit-costs", params={"q": "HIDDEN-COST"})
    assert costs.status_code == 200
    assert costs.json()["items"][0]["unit_cost_zar"] is None
