"""Owner user management and profile tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import UserRole
from tests.conftest import OWNER_EMAIL, OWNER_PASSWORD


@pytest.mark.parametrize("role", [r.value for r in UserRole if r != UserRole.OWNER])
async def test_owner_can_create_each_role(owner_client: AsyncClient, role: str) -> None:
    email = f"{role}-created@example.com"
    resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": "role-password",
            "role": role,
            "display_name": role.title(),
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == email
    assert body["role"] == role


async def test_owner_can_create_owner_role(owner_client: AsyncClient) -> None:
    resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "second-owner@example.com",
            "password": "owner-password",
            "role": "owner",
            "display_name": "Second Owner",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "second-owner@example.com"
    assert body["role"] == "owner"
    assert body["team"]["name"] == "Vellano"


async def test_owner_can_list_users(owner_client: AsyncClient) -> None:
    resp = await owner_client.get("/api/v1/users")
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 1
    owner = next(u for u in users if u["email"] == OWNER_EMAIL)
    assert owner["role"] == "owner"
    assert owner["team"]["name"] == "Vellano"
    assert owner["team_id"] == owner["team"]["id"]


async def test_non_owner_cannot_list_users(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    create_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "buyer-list@example.com",
            "password": "buyer-password",
            "role": "buyer",
        },
    )
    assert create_resp.status_code == 201

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer-list@example.com", "password": "buyer-password"},
    )
    assert login_resp.status_code == 200

    forbidden = await async_client.get("/api/v1/users")
    assert forbidden.status_code == 403


async def test_non_owner_cannot_create_user(
    async_client: AsyncClient,
) -> None:
    from app.config import settings

    async_client.cookies.clear()
    login_resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "buyer@example.com", "password": settings.seed_buyer_password},
    )
    assert login_resp.status_code == 200

    forbidden = await async_client.post(
        "/api/v1/users",
        json={
            "email": "another@example.com",
            "password": "another-password",
            "role": "warehouse",
        },
    )
    assert forbidden.status_code == 403


async def test_owner_can_edit_and_disable_user(owner_client: AsyncClient) -> None:
    create_resp = await owner_client.post(
        "/api/v1/users",
        json={
            "email": "editme@example.com",
            "password": "edit-password",
            "role": "till",
            "display_name": "Till User",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    patch_resp = await owner_client.patch(
        f"/api/v1/users/{user_id}",
        json={"display_name": "Updated Till", "role": "books", "is_disabled": True},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["display_name"] == "Updated Till"
    assert body["role"] == "books"
    assert body["is_disabled"] is True


async def test_profile_self_edit(owner_client: AsyncClient) -> None:
    resp = await owner_client.patch(
        "/api/v1/profile",
        json={"display_name": "Shop Owner", "password": "new-owner-pass"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Shop Owner"

    me_resp = await owner_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["display_name"] == "Shop Owner"

    owner_client.cookies.clear()
    new_login = await owner_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": "new-owner-pass"},
    )
    assert new_login.status_code == 200


async def test_exactly_one_team_after_seed(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    me_resp = await async_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    team_id = me_resp.json()["team"]["id"]

    create_resp = await async_client.post(
        "/api/v1/users",
        json={
            "email": "second@example.com",
            "password": "second-password",
            "role": "buyer",
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["team_id"] == team_id
