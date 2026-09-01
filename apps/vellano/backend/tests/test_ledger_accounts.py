"""S6 ledger chart of accounts tests."""

from __future__ import annotations

from httpx import AsyncClient


async def _account_balance(owner_client: AsyncClient, code: str) -> str:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    for account in resp.json():
        if account["code"] == code:
            return account["balance_zar"]
    raise AssertionError(f"Account {code} not found")


async def test_chart_of_accounts_seeded(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/accounts")
    assert resp.status_code == 200
    codes = {account["code"] for account in resp.json()}
    assert codes == {
        "1100",
        "1200",
        "1300",
        "2100",
        "2200",
        "4000",
        "5000",
        "6100",
    }


async def test_till_cannot_create_account(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "till-ledger@example.com",
            "password": "till-password",
            "role": "till",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "till-ledger@example.com", "password": "till-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post(
        "/api/v1/accounts",
        json={"code": "9999", "name": "Extra", "type": "expense"},
    )
    assert resp.status_code == 403

    list_resp = await async_client.get("/api/v1/accounts")
    assert list_resp.status_code == 200


async def test_books_can_create_account(
    async_client: AsyncClient,
    owner_client: AsyncClient,
) -> None:
    create_user = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "books-ledger@example.com",
            "password": "books-password",
            "role": "books",
        },
    )
    assert create_user.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "books-ledger@example.com", "password": "books-password"},
    )
    assert login_resp.status_code == 200

    resp = await async_client.post(
        "/api/v1/accounts",
        json={"code": "9999", "name": "Petty cash", "type": "asset"},
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == "9999"
    assert resp.json()["balance_zar"] in ("0", "0.00")


async def test_patch_account_name(owner_client: AsyncClient) -> None:
    accounts = (await owner_client.get("/api/v1/accounts")).json()
    bank = next(a for a in accounts if a["code"] == "1100")
    resp = await owner_client.patch(
        f"/api/v1/accounts/{bank['id']}",
        json={"name": "Main Bank"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Main Bank"
