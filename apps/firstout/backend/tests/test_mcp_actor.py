"""The in-process MCP actor seam and the permission keys each require_* dependency exposes."""

from __future__ import annotations

import asyncio
import uuid

import pytest
import sqlalchemy as sa
from fastapi import HTTPException

import app.dependencies.auth as dependencies
from app.config import settings
from app.middleware.auth import McpActor, mcp_actor, mcp_actor_ctx
from app.models.membership import Membership
from app.models.team import Team
from app.models.user import User
from app.permissions import PERMISSION_CATALOG_SET, ROLE_PRESETS
from tests.conftest import authenticate_as, create_test_staff

ME = "/api/v1/auth/me"
LOCATIONS = "/api/v1/locations"
REQUIRE = {
    name: dependency
    for name, dependency in vars(dependencies).items()
    if name.startswith("require_")
}
STAFF_ROLES = ("buyer", "warehouse", "till", "books")


async def _staff(client, role: str) -> tuple[User, Team]:
    record = await create_test_staff(client, email=f"mcp-actor-{role}@example.com", role=role)
    user = await client.test_db.get(User, uuid.UUID(record["id"]))
    return user, await client.test_db.get(Team, user.team_id)


async def test_actor_runs_real_routes_under_the_routes_own_permission_check(
    async_client, monkeypatch
):
    warehouse, team = await _staff(async_client, "warehouse")
    till, _ = await _staff(async_client, "till")
    bay = {"name": "Actor seam bay", "type": "warehouse"}
    assert "authorization" not in async_client.headers

    with mcp_actor(warehouse.id, team.clerk_org_id):
        me = await async_client.get(ME)
        created = await async_client.post(LOCATIONS, json=bay)
    assert (me.status_code, me.json()["id"]) == (200, str(warehouse.id))
    assert created.status_code == 201, created.text

    with mcp_actor(till.id, team.clerk_org_id):
        assert (await async_client.get(ME)).json()["id"] == str(till.id)
        refused = await async_client.post(LOCATIONS, json=bay)
    assert (refused.status_code, refused.json()["detail"]) == (403, "Forbidden")

    # The in-process request has no external host, so no Host value is needed or checked.
    monkeypatch.setattr(settings, "cookie_secure", True)
    with mcp_actor(warehouse.id, team.clerk_org_id):
        assert (
            await async_client.get(ME, headers={"Host": "in-process.invalid"})
        ).status_code == 200


async def test_external_request_cannot_become_an_actor(async_client):
    owner, team = await _staff(async_client, "owner")
    hostile = {
        "X-Mcp-Actor": str(owner.id),
        "X-Firstout-Mcp-Actor": f"{owner.id}:{team.clerk_org_id}",
        "X-User-Id": str(owner.id),
        "X-Clerk-Org-Id": team.clerk_org_id,
        "X-Forwarded-User": owner.email,
        "Cookie": f"mcp_actor={owner.id}; firstout_session={owner.id}",
    }
    body = {"mcp_actor": {"user_id": str(owner.id), "clerk_org_id": team.clerk_org_id}}

    assert (await async_client.get(ME, headers=hostile)).status_code == 401
    assert (await async_client.post(LOCATIONS, headers=hostile, json=body)).status_code == 401
    for scheme in ("Bearer", "McpActor"):
        forged = {**hostile, "Authorization": f"{scheme} {owner.id}"}
        assert (await async_client.get(ME, headers=forged)).status_code == 401

    # An actor held by another task, as during a concurrent MCP tool call, is not visible here.
    entered, release = asyncio.Event(), asyncio.Event()

    async def tool_call() -> None:
        with mcp_actor(owner.id, team.clerk_org_id):
            entered.set()
            await release.wait()

    tool = asyncio.create_task(tool_call())
    await entered.wait()
    try:
        assert (await async_client.get(ME, headers=hostile)).status_code == 401
    finally:
        release.set()
        await tool


async def test_actor_ends_with_its_block_and_never_combines_with_a_bearer(async_client):
    warehouse, team = await _staff(async_client, "warehouse")

    with mcp_actor(warehouse.id, team.clerk_org_id):
        assert (await async_client.get(ME)).status_code == 200
    assert mcp_actor_ctx.get() is None
    assert (await async_client.get(ME)).status_code == 401

    with pytest.raises(RuntimeError), mcp_actor(warehouse.id, team.clerk_org_id):
        raise RuntimeError("tool failed")
    assert mcp_actor_ctx.get() is None

    # A valid sign-in for someone else neither wins nor is silently ignored.
    assert (await authenticate_as(async_client, "owner@example.com")).status_code == 200
    with mcp_actor(warehouse.id, team.clerk_org_id):
        assert (await async_client.get(ME)).status_code == 401
    assert (await async_client.get(ME)).json()["role"] == "owner"


@pytest.mark.parametrize(
    ("breakage", "status"),
    [
        ("disabled_user", 401),
        ("system_user", 401),
        ("disabled_membership", 401),
        ("suspended_team", 403),
        ("other_organisation", 401),
        ("unknown_user", 401),
    ],
)
async def test_actor_is_refused_when_current_access_is_gone(async_client, breakage, status):
    db = async_client.test_db
    user, team = await _staff(async_client, "warehouse")
    actor = (user.id, team.clerk_org_id)
    with mcp_actor(*actor):
        assert (await async_client.get(ME)).status_code == 200

    if breakage == "disabled_user":
        user.is_disabled = True
    elif breakage == "system_user":
        user.role = "system"
    elif breakage == "disabled_membership":
        membership = await db.scalar(sa.select(Membership).where(Membership.user_id == user.id))
        membership.is_disabled = True
    elif breakage == "suspended_team":
        team.status = "suspended"
    elif breakage == "other_organisation":
        db.add(Team(slug="actor-other", name="Other", clerk_org_id="org_actor_other"))
        actor = (user.id, "org_actor_other")
    else:
        actor = (uuid.uuid4(), team.clerk_org_id)
    await db.flush()

    with mcp_actor(*actor):
        assert (await async_client.get(ME)).status_code == status
        assert (await async_client.post(LOCATIONS, json={})).status_code == status


@pytest.mark.no_db
def test_actor_needs_a_user_id_and_an_organisation():
    for user_id, organisation in (
        (uuid.uuid4(), ""),
        (str(uuid.uuid4()), "org_1"),
        (None, "org_1"),
    ):
        with pytest.raises(ValueError):
            McpActor(user_id, organisation)
        with pytest.raises(ValueError), mcp_actor(user_id, organisation):
            pass
    assert mcp_actor_ctx.get() is None


@pytest.mark.no_db
def test_every_require_dependency_exposes_catalog_keys():
    assert REQUIRE
    for name, dependency in REQUIRE.items():
        keys = dependency.permissions
        assert isinstance(keys, tuple) and keys, name
        assert set(keys) <= PERMISSION_CATALOG_SET, name
    assert len(set(REQUIRE.values())) == len(REQUIRE), "each name must stay its own dependency"


async def test_exposed_keys_are_the_keys_each_dependency_enforces(async_client):
    for role in STAFF_ROLES:
        user, _ = await _staff(async_client, role)
        for name, dependency in REQUIRE.items():
            permitted = not ROLE_PRESETS[role].isdisjoint(dependency.permissions)
            try:
                assert await dependency(user.id, async_client.test_db) == user.id
                allowed = True
            except HTTPException as exc:
                assert (exc.status_code, exc.detail) == (403, "Forbidden")
                allowed = False
            assert allowed == permitted, (role, name)


@pytest.mark.parametrize(
    ("dependency", "method", "path"),
    [
        (dependencies.require_transfer, "POST", "/api/v1/transfers"),
        (dependencies.require_books_mutate, "POST", "/api/v1/accounts"),
        (dependencies.require_customers_patch, "PATCH", f"/api/v1/customers/{uuid.uuid4()}"),
    ],
)
async def test_signed_in_requests_are_forbidden_exactly_without_an_exposed_key(
    async_client, dependency, method, path
):
    for role in STAFF_ROLES:
        user, _ = await _staff(async_client, role)
        assert (await authenticate_as(async_client, user.email)).status_code == 200
        response = await async_client.request(method, path, json={})
        permitted = not ROLE_PRESETS[role].isdisjoint(dependency.permissions)
        assert (response.status_code != 403) == permitted, (role, response.text)
