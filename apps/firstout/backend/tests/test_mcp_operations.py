"""Exercise the independent staff review boundary and durable request replay against Postgres."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from app.config import settings
from app.database import tenant_session
from app.dependencies.tenant_signup import get_clerk_api
from app.main import app
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpActionActivity
from app.models.membership import Membership
from app.models.role import Role, RolePermission
from app.exceptions import ForbiddenError
from app.crud.role import RoleCRUD
from app.crud.user import UserCRUD
from app.permissions import STOCK_COST_VIEW
from app.services import mcp_operations
from app.services.clerk_api import ClerkAPI
from app.services.mcp_actions import ACTIONS
from app.services.mcp_domains import Action
from f0rge_db.crud import unit_of_work
from tests.test_mcp_tokens import _bearer, _clerk, _issue, _rpc, mcp_fixture  # noqa: F401


class Change(BaseModel):
    quantity: int


@pytest.fixture
async def operation_review(mcp_fixture, monkeypatch):  # noqa: F811
    client, teams, users, boundary = mcp_fixture
    changes = []
    snapshot = {"item": "Showroom chair", "quantity": 1}

    async def preview(db, token, name, args):
        return dict(snapshot)

    async def execute(db, token, args):
        changes.append(args.quantity)
        return {"quantity": args.quantity}

    action = Action(
        "test_review", "Warehouse", "Test review", Change, (STOCK_COST_VIEW,), execute, "review"
    )
    direct = Action(
        "test_draft", "Warehouse", "Test draft", Change, (STOCK_COST_VIEW,), execute, "write"
    )
    monkeypatch.setitem(ACTIONS, action.name, action)
    monkeypatch.setitem(ACTIONS, direct.name, direct)
    monkeypatch.setattr(mcp_operations, "TRANSFER_ACTIONS", (action,))
    monkeypatch.setattr(mcp_operations, "preview_transfer", preview)
    async with httpx.AsyncClient(transport=httpx.MockTransport(boundary.respond)) as provider_http:

        def provider():
            return ClerkAPI(provider_http, "fixture-mcp-clerk-key")

        monkeypatch.setitem(app.dependency_overrides, get_clerk_api, provider)
        staff = _clerk(users[0], teams[0])
        issued = (await _issue(client, staff)).json()
        yield client, teams, users, boundary, staff, issued, changes, snapshot


async def tool(client, secret, name, args):
    response = await _rpc(client, secret, "tools/call", {"name": name, "arguments": args})
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    if not result["isError"] and "structuredContent" not in result:
        result["structuredContent"] = json.loads(result["content"][0]["text"])
    return result


async def write(client, secret, action, request_id, quantity=1):
    return await tool(
        client,
        secret,
        "request_write",
        {"action": action, "arguments": {"quantity": quantity}, "request_id": str(request_id)},
    )


async def test_review_is_bound_to_member_business_payload_and_live_permissions(
    operation_review, monkeypatch
):
    client, teams, users, boundary, staff, issued, changes, snapshot = operation_review
    secret = issued["secret"]
    request_id = uuid.uuid4()
    review_request = await write(client, secret, "test_review", request_id)
    assert not review_request["isError"], review_request
    first = review_request["structuredContent"]
    assert first["status"] == "awaiting_confirmation"
    path = "/api/v1/mcp-operations/" + first["operation_id"]
    assert first["review_url"].endswith("/review/" + first["operation_id"])
    assert (await client.get(path, headers=_bearer(secret))).status_code == 401
    for headers in (_clerk(users[1], teams[0]), _clerk(users[0], teams[1])):
        assert (await client.get(path, headers=headers)).status_code == 404
        assert (await client.post(path + "/confirm", headers=headers)).status_code == 404
    review = await client.get(path, headers=staff)
    assert review.status_code == 200, review.text
    assert review.headers["cache-control"] == "no-store"
    assert review.json()["preview"] == snapshot
    assert changes == []
    assert (await write(client, secret, "test_review", request_id, 2))["isError"]
    assert (await write(client, secret, "test_review", request_id))["structuredContent"] == first
    method = {"action": "operations_lookup", "arguments": {"request_id": str(request_id)}}
    assert (await tool(client, secret, "run_read", method))["structuredContent"] == first

    # A previously validated staff JWT does not bypass a later provider removal.
    identity = (teams[0].clerk_org_id, users[0].clerk_user_id)
    boundary.memberships.remove(identity)
    assert (await client.post(path + "/confirm", headers=staff)).status_code == 403
    boundary.memberships.add(identity)
    # Or a valid membership that no longer has the required permission.
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(
            update(Membership)
            .where(Membership.user_id == users[0].id, Membership.team_id == teams[0].id)
            .values(is_legacy_home=False, role="no_permissions")
        )
    assert (await client.post(path + "/confirm", headers=staff)).status_code == 403
    assert (await tool(client, secret, "run_read", method))["isError"]
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(
            update(Membership)
            .where(Membership.user_id == users[0].id, Membership.team_id == teams[0].id)
            .values(is_legacy_home=True, role="reader")
        )

    with monkeypatch.context() as patch:
        patch.setattr(settings, "mcp_writes_enabled", False)
        assert (await client.get(path, headers=staff)).status_code == 200
        assert (await client.post(path + "/confirm", headers=staff)).status_code == 403
    snapshot["quantity"] = 2
    assert (await client.post(path + "/confirm", headers=staff)).status_code == 409
    assert changes == []
    snapshot["quantity"] = 1
    left, right = await asyncio.gather(
        *(client.post(path + "/confirm", headers=staff) for _ in range(2))
    )
    assert left.status_code == right.status_code == 200
    assert left.json() == right.json()
    assert left.json()["status"] == "completed"
    assert changes == [1]
    with monkeypatch.context() as patch:
        patch.setattr(settings, "mcp_writes_enabled", False)
        assert (await client.post(path + "/confirm", headers=staff)).json()["status"] == "completed"
    assert (await tool(client, secret, "run_read", method))["structuredContent"]["result"] == {
        "quantity": 1
    }
    async with tenant_session(teams[0].id) as db:
        events = list(
            await db.scalars(
                select(McpActionActivity).where(
                    McpActionActivity.operation_id == uuid.UUID(first["operation_id"]),
                    McpActionActivity.action == "write_confirmed",
                )
            )
        )
        assert sorted(event.result for event in events) == [
            "denied",
            "denied",
            "denied",
            "failed",
            "success",
        ]
        assert {event.user_id for event in events} == {users[0].id}
        assert {event.token_id for event in events} == {uuid.UUID(issued["token"]["id"])}
        assert (events[0].user_id, events[0].token_id, events[0].source) == (
            users[0].id,
            uuid.UUID(issued["token"]["id"]),
            "firstout",
        )


async def test_request_retries_expiry_and_rotation(operation_review):
    client, teams, users, _boundary, staff, issued, changes, _snapshot = operation_review
    secret = issued["secret"]
    request_id = uuid.uuid4()
    both = await asyncio.gather(
        *(write(client, secret, "test_draft", request_id) for _ in range(2))
    )
    assert not both[0]["isError"], both[0]
    assert both[0]["structuredContent"] == both[1]["structuredContent"]
    assert both[0]["structuredContent"]["status"] == "completed"
    assert changes == [1]

    first = (await write(client, secret, "test_review", uuid.uuid4()))["structuredContent"]
    path = "/api/v1/mcp-operations/" + first["operation_id"]
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(
            update(McpOperation)
            .where(McpOperation.id == uuid.UUID(first["operation_id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    assert (await client.get(path, headers=staff)).json()["status"] == "expired"
    assert (await client.post(path + "/confirm", headers=staff)).status_code == 410

    second = (await write(client, secret, "test_review", uuid.uuid4()))["structuredContent"]
    token_id = issued["token"]["id"]
    rotated = await client.post(
        f"/api/v1/mcp-tokens/{token_id}/rotate",
        headers=staff,
        json={"version": issued["token"]["version"]},
    )
    assert rotated.status_code == 200
    invalid = await client.post(
        "/api/v1/mcp-operations/" + second["operation_id"] + "/confirm", headers=staff
    )
    assert invalid.status_code == 403
    lookup = await tool(
        client,
        rotated.json()["secret"],
        "run_read",
        {
            "action": "operations_lookup",
            "arguments": {"request_id": str(request_id)},
        },
    )
    assert lookup["isError"]
    assert changes == [1]


async def test_confirmation_refreshes_cached_cross_business_role_after_provider_check(
    operation_review,
):
    client, teams, users, _boundary, _staff, _issued, changes, _snapshot = operation_review
    team, user = teams[1], users[0]
    issued = (await _issue(client, _clerk(user, team))).json()
    pending = (await write(client, issued["secret"], "test_review", uuid.uuid4()))[
        "structuredContent"
    ]

    class DemoteDuringProviderCheck:
        async def staff_access_active(self, subject, organisation):
            assert (subject, organisation) == (user.clerk_user_id, team.clerk_org_id)
            async with tenant_session(team.id) as update_db, unit_of_work(update_db):
                role_id = select(Role.id).where(Role.team_id == team.id, Role.slug == "reader")
                await update_db.execute(
                    delete(RolePermission).where(
                        RolePermission.role_id.in_(role_id), RolePermission.key == STOCK_COST_VIEW
                    )
                )
            return True

    async with tenant_session(team.id) as db:
        # Hold these objects across the provider await just like an earlier request dependency can.
        member = await db.scalar(
            select(Membership).where(Membership.user_id == user.id, Membership.team_id == team.id)
        )
        staff = await UserCRUD(db).get_by_id(user.id)
        role = await RoleCRUD(db).get_by_slug("reader")
        assert not member.is_legacy_home and member.role == staff.role == "reader"
        assert [p.key for p in role.permissions] == [STOCK_COST_VIEW]
        with pytest.raises(ForbiddenError, match="permission"):
            await mcp_operations.confirm_staff_review(
                db,
                team.id,
                user.id,
                uuid.UUID(pending["operation_id"]),
                DemoteDuringProviderCheck(),
            )
    assert changes == []
