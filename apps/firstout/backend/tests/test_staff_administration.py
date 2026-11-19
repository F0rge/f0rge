from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from app.config import settings
from app.crud.user import TeamCRUD
from app.dependencies.tenant_signup import get_clerk_api
from app.main import app
from app.models.role import Role, RolePermission
from app.models.user import User
from app.permissions import USERS_MANAGE
from f0rge_core.exceptions import ExternalServiceError
from f0rge_db.crud import unit_of_work
from tests.conftest import authenticate_as, create_test_staff, OWNER_EMAIL

_CAPACITY = "/api/v1/organisations/current/staff-capacity"
_INVITATIONS = "/api/v1/organisations/current/invitations"


async def test_delegated_directory_invite_capacity_retry_and_owner_protections(
    owner_client, async_db, monkeypatch
):
    owner_id = (await owner_client.get("/api/v1/auth/me")).json()["id"]
    role = Role(name="Staff administration fixture", slug="staff-administration-fixture")
    async_db.add(role)
    await async_db.flush()
    async_db.add(RolePermission(role_id=role.id, key=USERS_MANAGE))
    manager = await create_test_staff(
        owner_client, email="manager@example.com", role=role.slug, display_name="Manager"
    )
    regular = await create_test_staff(owner_client, email="ordinary-staff@example.com", role="till")
    async with unit_of_work(async_db):
        pass
    monkeypatch.setattr(settings, "tenant_signup_enabled", False)
    monkeypatch.setattr(settings, "clerk_secret_key", "fixture-key")
    remote = SimpleNamespace(
        members=AsyncMock(return_value=[{"id": f"orgmem_{index}"} for index in range(10)]),
        organisation=AsyncMock(return_value={"max_allowed_memberships": 11}),
        invite=AsyncMock(
            side_effect=[
                ExternalServiceError("Clerk temporarily unavailable"),
                {"id": "orginv_fixture"},
            ]
        ),
        revoke_invitation=AsyncMock(),
    )
    monkeypatch.setitem(app.dependency_overrides, get_clerk_api, lambda: remote)
    assert (await authenticate_as(owner_client, regular["email"])).status_code == 200
    assert (await owner_client.get(_CAPACITY)).status_code == 403
    assert (await owner_client.get(_INVITATIONS)).status_code == 403

    assert (await authenticate_as(owner_client, manager["email"])).status_code == 200
    assert (await owner_client.get("/api/v1/users")).status_code == 200
    capacity = (await owner_client.get(_CAPACITY)).json()
    assert set(capacity) == {"active_count", "member_count", "pending_count", "max_members"}
    assert capacity["active_count"] < capacity["member_count"] == 10
    assert capacity["pending_count"] == 0
    assert capacity["max_members"] == 11

    assert (
        await owner_client.patch(f"/api/v1/users/{owner_id}", json={"is_disabled": True})
    ).status_code == 403
    assert (
        await owner_client.patch(f"/api/v1/users/{regular['id']}", json={"role": "owner"})
    ).status_code == 403
    assert (
        await owner_client.post(
            _INVITATIONS, json={"email": "new-owner@example.com", "role": "owner"}
        )
    ).status_code == 403
    assert (
        await owner_client.patch(f"/api/v1/users/{manager['id']}", json={"role": "till"})
    ).status_code == 409
    own_profile = await owner_client.patch(
        f"/api/v1/users/{manager['id']}", json={"display_name": "Staff Manager"}
    )
    assert own_profile.json()["display_name"] == "Staff Manager"
    assert own_profile.json()["can_edit_display_name"] is True

    invitation = {"email": "new-staff@example.com", "role": "till"}
    assert (await owner_client.post(_INVITATIONS, json=invitation)).status_code == 502
    pending = (await owner_client.get(_INVITATIONS)).json()[0]
    assert pending["status"] == "pending" and pending["delivery_confirmed"] is False
    assert (await owner_client.get(_CAPACITY)).json()["pending_count"] == 1
    full = await owner_client.post(
        _INVITATIONS, json={"email": "other-staff@example.com", "role": "till"}
    )
    assert full.status_code == 400 and "supports 11 staff" in full.json()["detail"]
    retried = await owner_client.post(_INVITATIONS, json=invitation)
    assert retried.status_code == 201
    assert retried.json()["delivery_confirmed"] is True and retried.json()["id"] == pending["id"]
    assert remote.invite.await_count == 2
    assert (await owner_client.delete(f"{_INVITATIONS}/{pending['id']}")).status_code == 204
    assert (await owner_client.get(_CAPACITY)).json()["pending_count"] == 0
    assert (await authenticate_as(owner_client, OWNER_EMAIL)).status_code == 200


@pytest.mark.parametrize("mutation", ["member grant", "owner invite", "owner revoke"])
async def test_owner_operations_recheck_permission_after_the_team_lock(
    owner_client, async_db, monkeypatch, mutation
):
    owner_id = (await owner_client.get("/api/v1/auth/me")).json()["id"]
    acting_owner = await create_test_staff(
        owner_client, email="acting-owner@example.com", role="owner"
    )
    manager = Role(name="Delegated managers", slug="delegated-managers")
    async_db.add(manager)
    await async_db.flush()
    async_db.add(RolePermission(role_id=manager.id, key=USERS_MANAGE))
    async with unit_of_work(async_db):
        pass

    monkeypatch.setattr(settings, "clerk_secret_key", "fixture-key")
    provider = SimpleNamespace(
        members=AsyncMock(return_value=[]),
        organisation=AsyncMock(return_value={"max_allowed_memberships": 10}),
        invite=AsyncMock(return_value={"id": "orginv_fixture"}),
        revoke_invitation=AsyncMock(),
    )
    monkeypatch.setitem(app.dependency_overrides, get_clerk_api, lambda: provider)

    request_data = {"email": "pending-owner@example.com", "role": "owner"}
    pending = None
    if mutation == "owner revoke":
        accepted = await owner_client.post(_INVITATIONS, json=request_data)
        assert accepted.status_code == 201
        pending = accepted.json()["id"]
        provider.invite.reset_mock()

    assert (await authenticate_as(owner_client, acting_owner["email"])).status_code == 200
    lock_current = TeamCRUD.lock_current

    async def lock_after_owner_role_changes(crud):
        # Simulate the change that committed while the request held a cached
        # owner identity and was waiting for the same team lock.
        await lock_current(crud)
        await crud.db.execute(
            update(User)
            .where(User.id == uuid.UUID(acting_owner["id"]))
            .values(role=manager.slug)
            .execution_options(synchronize_session=False)
        )

    monkeypatch.setattr(TeamCRUD, "lock_current", lock_after_owner_role_changes)
    if mutation == "member grant":
        response = await owner_client.patch(f"/api/v1/users/{owner_id}", json={"is_disabled": True})
    elif mutation == "owner invite":
        response = await owner_client.post(_INVITATIONS, json=request_data)
    else:
        response = await owner_client.delete(f"{_INVITATIONS}/{pending}")

    assert response.status_code == 403, response.text
    assert "Only an owner" in response.json()["detail"]
    provider.invite.assert_not_awaited()
    provider.revoke_invitation.assert_not_awaited()
