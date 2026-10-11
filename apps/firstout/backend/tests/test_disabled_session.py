"""A disabled employee's existing session must not keep working."""

from __future__ import annotations

from httpx import AsyncClient

from app.config import settings
from app.services.auth import JWT_COOKIE_NAME


async def test_disabled_warehouse_session_cannot_read_or_create_locations(
    async_client: AsyncClient,
) -> None:
    login = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": "warehouse@example.com",
            "password": settings.seed_warehouse_password,
        },
    )
    assert login.status_code == 200
    warehouse_session = async_client.cookies.get(JWT_COOKIE_NAME)
    assert warehouse_session

    before = await async_client.get("/api/v1/locations")
    assert before.status_code == 200
    location_count = len(before.json())

    async_client.cookies.clear()
    owner = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.seed_owner_email,
            "password": settings.seed_owner_password,
        },
    )
    assert owner.status_code == 200
    users = await async_client.get("/api/v1/users")
    assert users.status_code == 200
    warehouse = next(user for user in users.json() if user["email"] == "warehouse@example.com")
    disabled = await async_client.patch(
        f"/api/v1/users/{warehouse['id']}",
        json={"is_disabled": True},
    )
    assert disabled.status_code == 200

    async_client.cookies.clear()
    async_client.cookies.set(JWT_COOKIE_NAME, warehouse_session)

    me = await async_client.get("/api/v1/auth/me")
    assert me.status_code == 401

    listed = await async_client.get("/api/v1/locations")
    assert listed.status_code == 401

    created = await async_client.post(
        "/api/v1/locations",
        json={"name": "Disabled session shed", "type": "warehouse"},
    )
    assert created.status_code == 401

    async_client.cookies.clear()
    owner_again = await async_client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.seed_owner_email,
            "password": settings.seed_owner_password,
        },
    )
    assert owner_again.status_code == 200
    after = await async_client.get("/api/v1/locations")
    assert after.status_code == 200
    assert len(after.json()) == location_count
    assert all(row["name"] != "Disabled session shed" for row in after.json())
