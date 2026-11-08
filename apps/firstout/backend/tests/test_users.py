"""Clerk-linked staff keep local permissions and profile preferences."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from tests.conftest import OWNER_EMAIL, authenticate_as, create_test_staff
from tests.test_purchase_orders import _location_id_by_name


@pytest.mark.parametrize("role", [r.value for r in UserRole])
async def test_owner_cannot_create_local_password_accounts(
    owner_client: AsyncClient, async_db: AsyncSession, role: str
) -> None:
    email = f"retired-create-{role}@example.com"
    response = await owner_client.post(
        "/api/v1/users",
        json={"email": email, "password": "local-password", "role": role},
    )
    assert response.status_code == 400
    assert "invit" in response.json()["detail"].lower()
    assert await async_db.scalar(select(User).where(User.email == email)) is None


async def test_owner_can_list_preserved_users(owner_client: AsyncClient) -> None:
    response = await owner_client.get("/api/v1/users")
    assert response.status_code == 200
    owner = next(row for row in response.json() if row["email"] == OWNER_EMAIL)
    assert owner["role"] == "owner"
    assert owner["team"]["name"] == "Firstout"
    assert owner["team_id"] == owner["team"]["id"]


async def test_non_owner_cannot_list_users(owner_client: AsyncClient) -> None:
    await create_test_staff(owner_client, email="buyer-list@example.com", role="buyer")
    assert (await authenticate_as(owner_client, "buyer-list@example.com")).status_code == 200
    assert (await owner_client.get("/api/v1/users")).status_code == 403


async def test_non_owner_cannot_create_user(async_client: AsyncClient) -> None:
    assert (await authenticate_as(async_client, "buyer@example.com")).status_code == 200
    response = await async_client.post(
        "/api/v1/users",
        json={"email": "another@example.com", "password": "another-password", "role": "warehouse"},
    )
    assert response.status_code == 403


async def test_owner_can_edit_local_role_display_name_and_disabled_membership(
    owner_client: AsyncClient,
) -> None:
    user = await create_test_staff(
        owner_client, email="editme@example.com", role="till", display_name="Till User"
    )
    response = await owner_client.patch(
        f"/api/v1/users/{user['id']}",
        json={"display_name": "Updated Till", "role": "books", "is_disabled": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Updated Till"
    assert body["role"] == "books" and body["is_disabled"] is True


async def test_disabled_home_owner_cannot_count_as_remaining_owner(
    owner_client: AsyncClient,
) -> None:
    other = await create_test_staff(owner_client, email="disabled-owner@example.com", role="owner")
    disabled = await owner_client.patch(f"/api/v1/users/{other['id']}", json={"is_disabled": True})
    assert disabled.status_code == 200 and disabled.json()["is_disabled"] is True
    owner_id = (await owner_client.get("/api/v1/auth/me")).json()["id"]
    for update in ({"is_disabled": True}, {"role": "buyer"}):
        response = await owner_client.patch(f"/api/v1/users/{owner_id}", json=update)
        assert response.status_code == 409
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200


@pytest.mark.parametrize("target", ["profile", "user"])
@pytest.mark.parametrize(
    "field,value", [("email", "must-not-change@example.com"), ("password", "must-not-change")]
)
async def test_local_identity_credentials_cannot_be_changed(
    owner_client: AsyncClient, async_db: AsyncSession, target: str, field: str, value: str
) -> None:
    owner = await async_db.scalar(select(User).where(User.email == OWNER_EMAIL))
    before = (owner.email, owner.password_hash, owner.token_version, owner.clerk_user_id)
    path = "/api/v1/profile" if target == "profile" else f"/api/v1/users/{owner.id}"
    response = await owner_client.patch(path, json={field: value})
    assert response.status_code == 422
    assert any(error["loc"][-1] == field for error in response.json()["detail"])
    await async_db.refresh(owner)
    assert (owner.email, owner.password_hash, owner.token_version, owner.clerk_user_id) == before
    assert (await owner_client.get("/api/v1/auth/me")).status_code == 200


async def test_profile_self_edit_does_not_require_a_local_password(
    owner_client: AsyncClient,
) -> None:
    response = await owner_client.patch("/api/v1/profile", json={"display_name": "Shop Owner"})
    assert response.status_code == 200 and response.json()["display_name"] == "Shop Owner"
    me = await owner_client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["display_name"] == "Shop Owner"


async def test_linked_fixture_staff_stay_in_original_team(owner_client: AsyncClient) -> None:
    team_id = (await owner_client.get("/api/v1/auth/me")).json()["team"]["id"]
    other = await create_test_staff(owner_client, email="second@example.com", role="buyer")
    listed = (await owner_client.get("/api/v1/users")).json()
    assert next(row for row in listed if row["id"] == other["id"])["team_id"] == team_id


async def test_signed_till_preserves_seeded_default_location(owner_client: AsyncClient) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    response = await authenticate_as(owner_client, "till@example.com")
    assert response.status_code == 200
    assert response.json()["default_location_id"] == bedford_id


async def test_profile_set_and_clear_default_location(owner_client: AsyncClient) -> None:
    bedford_id = await _location_id_by_name(owner_client, "Bedfordview")
    kramerville_id = await _location_id_by_name(owner_client, "Kramerville")
    for location in (kramerville_id, None, bedford_id):
        response = await owner_client.patch(
            "/api/v1/profile", json={"default_location_id": location}
        )
        assert response.status_code == 200
        assert response.json()["default_location_id"] == location
