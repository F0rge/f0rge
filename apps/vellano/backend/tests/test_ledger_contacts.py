"""S6 ledger contacts tests."""

from __future__ import annotations

from httpx import AsyncClient


async def test_create_customer_and_list_contacts(owner_client: AsyncClient) -> None:
    supplier_resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Factory Co", "default_currency": "USD"},
    )
    assert supplier_resp.status_code == 201

    customer_resp = await owner_client.post(
        "/api/v1/contacts",
        json={"name": "Jane Retail", "email": "jane@example.com"},
    )
    assert customer_resp.status_code == 201
    body = customer_resp.json()
    assert body["kind"] == "customer"
    assert body["name"] == "Jane Retail"
    assert body["currency"] is None

    list_resp = await owner_client.get("/api/v1/contacts")
    assert list_resp.status_code == 200
    contacts = list_resp.json()
    kinds = {(c["kind"], c["name"]) for c in contacts}
    assert ("customer", "Jane Retail") in kinds
    assert ("supplier", "Factory Co") in kinds
