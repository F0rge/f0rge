"""S5 SKU wholesale/retail VAT price tests."""

from __future__ import annotations

from httpx import AsyncClient


async def _create_sku(owner_client: AsyncClient, suffix: str) -> dict:
    resp = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": f"VEL-PRICE-{suffix}",
            "our_barcode": f"BAR-PRICE-{suffix}",
            "name": f"Price test {suffix}",
            "design": f"Design {suffix}",
            "fabric": f"Fabric {suffix}",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def test_create_sku_prices_null(owner_client: AsyncClient) -> None:
    body = await _create_sku(owner_client, "NULL")
    assert body["wholesale_ex_vat"] is None
    assert body["wholesale_inc_vat"] is None
    assert body["retail_ex_vat"] is None
    assert body["retail_inc_vat"] is None


async def test_patch_wholesale_ex_vat_derives_inc(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "WEX")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["wholesale_ex_vat"] == "100.00"
    assert body["wholesale_inc_vat"] == "115.00"


async def test_patch_retail_inc_vat_derives_ex(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "RINC")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_inc_vat": "2300.00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["retail_inc_vat"] == "2300.00"
    assert body["retail_ex_vat"] == "2000.00"


async def test_inc_to_ex_round_half_up(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "ROUND")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_inc_vat": "2500.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["retail_ex_vat"] == "2173.91"


async def test_vat_rate_is_fifteen_percent(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "VAT15")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["wholesale_inc_vat"] == "115.00"
    assert resp.json()["wholesale_inc_vat"] != "114.00"


async def test_unauthenticated_patch_returns_401(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "UNAUTH")
    async_client.cookies.clear()
    resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert resp.status_code == 401


async def test_till_cannot_patch_prices_but_can_get(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "TILL")
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-price@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-price@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 403

    get_resp = await async_client.get(f"/api/v1/skus/{sku['id']}")
    assert get_resp.status_code == 200


async def test_books_cannot_patch_prices_but_can_list(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    await _create_sku(owner_client, "BOOKS")
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-price@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-price@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    list_resp = await async_client.get("/api/v1/skus")
    assert list_resp.status_code == 200

    sku_id = list_resp.json()[0]["id"]
    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku_id}",
        json={"retail_ex_vat": "50.00"},
    )
    assert patch_resp.status_code == 403


async def test_warehouse_cannot_patch_prices(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "WH")
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "warehouse-price@example.com",
            "password": "warehouse-password",
            "role": "warehouse",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "warehouse-price@example.com", "password": "warehouse-password"},
    )
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 403


async def test_buyer_can_patch_prices(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "BUYER")
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-price@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-price@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200

    patch_resp = await async_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["wholesale_inc_vat"] == "115.00"


async def test_both_ex_and_inc_wholesale_returns_validation_error(
    owner_client: AsyncClient,
) -> None:
    sku = await _create_sku(owner_client, "BOTH-W")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00", "wholesale_inc_vat": "115.00"},
    )
    assert resp.status_code == 400


async def test_negative_price_returns_validation_error(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "NEG")
    resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": "-1.00"},
    )
    assert resp.status_code == 400


async def test_clear_price_with_null_ex(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "CLEAR")
    set_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": "100.00"},
    )
    assert set_resp.status_code == 200

    clear_resp = await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"retail_ex_vat": None},
    )
    assert clear_resp.status_code == 200
    body = clear_resp.json()
    assert body["retail_ex_vat"] is None
    assert body["retail_inc_vat"] is None


async def test_list_and_get_include_price_fields(owner_client: AsyncClient) -> None:
    sku = await _create_sku(owner_client, "LIST")
    await owner_client.patch(
        f"/api/v1/skus/{sku['id']}",
        json={"wholesale_ex_vat": "100.00", "retail_inc_vat": "2300.00"},
    )

    get_resp = await owner_client.get(f"/api/v1/skus/{sku['id']}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["wholesale_inc_vat"] == "115.00"
    assert body["retail_ex_vat"] == "2000.00"

    list_resp = await owner_client.get("/api/v1/skus")
    assert list_resp.status_code == 200
    listed = next(item for item in list_resp.json() if item["id"] == sku["id"])
    assert listed["wholesale_inc_vat"] == "115.00"
    assert listed["retail_ex_vat"] == "2000.00"
