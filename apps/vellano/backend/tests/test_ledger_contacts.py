"""Books contacts API is gone; customers and suppliers stay separate."""

from __future__ import annotations

from httpx import AsyncClient


async def test_contacts_api_is_removed(owner_client: AsyncClient) -> None:
    get_resp = await owner_client.get("/api/v1/contacts")
    assert get_resp.status_code == 404
    post_resp = await owner_client.post("/api/v1/contacts", json={"name": "Nope"})
    assert post_resp.status_code == 404

    supplier_resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Factory Co", "default_currency": "USD"},
    )
    assert supplier_resp.status_code == 201

    customer_resp = await owner_client.post(
        "/api/v1/customers",
        json={"name": "Jane Retail", "email": "jane@example.com"},
    )
    assert customer_resp.status_code == 201
    body = customer_resp.json()
    assert body["name"] == "Jane Retail"
    assert body["email"] == "jane@example.com"

    customers = (await owner_client.get("/api/v1/customers")).json()
    suppliers = (await owner_client.get("/api/v1/suppliers")).json()
    assert any(row["name"] == "Jane Retail" for row in customers)
    assert any(row["name"] == "Factory Co" for row in suppliers)
