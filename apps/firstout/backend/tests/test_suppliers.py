"""S3 catalogue suppliers API tests."""

from __future__ import annotations

from tests.conftest import authenticate_as, create_test_staff

from httpx import AsyncClient


async def test_create_supplier_defaults_currency_to_usd(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Acme Imports"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Acme Imports"
    assert body["default_currency"] == "USD"


async def test_create_supplier_explicit_currency(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Euro Supplier", "default_currency": "eur"},
    )
    assert resp.status_code == 201
    assert resp.json()["default_currency"] == "EUR"


async def test_list_suppliers_authenticated(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/suppliers",
        json={"name": "Listed Supplier"},
    )
    assert create_resp.status_code == 201

    list_resp = await owner_client.get("/api/v1/suppliers")
    assert list_resp.status_code == 200
    names = {row["name"] for row in list_resp.json()}
    assert "Listed Supplier" in names


async def test_unauthenticated_suppliers_return_401(async_client: AsyncClient) -> None:
    assert (await async_client.get("/api/v1/suppliers")).status_code == 401
    post_resp = await async_client.post(
        "/api/v1/suppliers",
        json={"name": "No auth"},
    )
    assert post_resp.status_code == 401


async def test_buyer_can_mutate_suppliers(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await create_test_staff(
        owner_client,
        **{
            "email": "buyer-suppliers@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "buyer-suppliers@example.com")
    assert login_resp.status_code == 200

    create_resp = await async_client.post(
        "/api/v1/suppliers",
        json={"name": "Buyer Supplier"},
    )
    assert create_resp.status_code == 201


async def test_warehouse_can_list_but_not_create_suppliers(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await create_test_staff(
        owner_client,
        **{
            "email": "warehouse-suppliers@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )

    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    login_resp = await authenticate_as(async_client, "warehouse-suppliers@example.com")
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/suppliers")
    assert list_resp.status_code == 200

    post_resp = await async_client.post(
        "/api/v1/suppliers",
        json={"name": "Warehouse create"},
    )
    assert post_resp.status_code == 403
