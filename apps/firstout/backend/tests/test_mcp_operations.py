"""Durable receipts and safe replay across the change from reviewed to direct writes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.database import tenant_session
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpActionActivity, McpToken
from app.services.mcp_tokens import McpTokenService
from app.models.role import Role, RolePermission
from app.permissions import STOCK_TRANSFER
from f0rge_db.crud import unit_of_work
from tests.test_mcp_tokens import _clerk, _issue, _rpc, mcp_fixture  # noqa: F401


async def _tool(client, secret, name, **arguments):
    reply = await _rpc(client, secret, "tools/call", {"name": name, "arguments": arguments})
    assert reply.status_code == 200, reply.text
    return reply.json()["result"]


async def _grant_transfers(db, team_id):
    role_id = await db.scalar(select(Role.id).where(Role.team_id == team_id, Role.slug == "reader"))
    db.add(RolePermission(team_id=team_id, role_id=role_id, key=STOCK_TRANSFER))


async def _historical_operation(client, team, user, *, result=None, expires_at=None):
    """Model a receipt written by the previous release with exactly its stored fields."""
    staff = _clerk(user, team)
    issued = (await _issue(client, staff)).json()
    token = issued["token"]
    arguments = {"transfer_id": str(uuid.uuid4())}
    async with tenant_session(team.id) as db, unit_of_work(db):
        await _grant_transfers(db, team.id)
        op = McpOperation(
            team_id=team.id,
            user_id=user.id,
            token_id=uuid.UUID(token["id"]),
            token_version=token["version"],
            request_id=uuid.uuid4(),
            action_name="transfers_dispatch",
            arguments=arguments,
            preview={"quantity": "2"},
            expires_at=expires_at,
            result=result,
            completed_at=datetime.now(UTC) if result is not None else None,
            confirmed_by=user.id if result is not None else None,
        )
        db.add(op)
        await db.flush()
        issuer = await db.get(McpToken, op.token_id)
        audit = McpTokenService(db, team.id)
        audit.record(
            issuer, "write_requested", "mcp", action_name=op.action_name, operation_id=op.id
        )
        if result is not None:
            audit.record(
                issuer,
                "write_confirmed",
                "firstout",
                action_name=op.action_name,
                operation_id=op.id,
            )
    return issued, op


async def _audit_summaries(client, team, user, op):
    reply = await client.get(
        "/api/v1/audit/events",
        headers=_clerk(user, team),
        params={"source": "mcp", "q": str(op.id)},
    )
    assert reply.status_code == 200, reply.text
    rows = reply.json()["items"]
    assert all(row["operation_id"] == str(op.id) for row in rows)
    return [(row["summary"], row["origin"]) for row in rows]


async def _lookup(client, secret, op):
    return await _tool(
        client,
        secret,
        "run_read",
        action="operations_lookup",
        arguments={"request_id": str(op.request_id)},
    )


async def _replay(client, secret, op, arguments=None):
    return await _tool(
        client,
        secret,
        "run_write",
        action=op.action_name,
        request_id=str(op.request_id),
        arguments=op.arguments if arguments is None else arguments,
    )


@pytest.mark.parametrize("minutes", [-60, 10], ids=["expired", "still-pending"])
async def test_old_unconfirmed_operation_is_terminal_and_staff_confirm_route_is_retired(
    mcp_fixture,  # noqa: F811
    minutes,
):
    client, teams, users, _ = mcp_fixture
    team, user = teams[0], users[0]
    issued, op = await _historical_operation(
        client, team, user, expires_at=datetime.now(UTC) + timedelta(minutes=minutes)
    )
    secret = issued["secret"]
    lookup = await _lookup(client, secret, op)
    assert not lookup["isError"], lookup
    receipt = lookup["structuredContent"]
    assert receipt["status"] == "not_executed"
    assert "review_url" not in receipt and "result" not in receipt
    summaries = await _audit_summaries(client, team, user, op)
    assert len(summaries) == 1 and "write requested" in summaries[0][0]
    assert summaries[0][1] == "mcp"
    replay = await _replay(client, secret, op)
    assert not replay["isError"] and replay["structuredContent"] == receipt
    conflicting = await _replay(client, secret, op, {"transfer_id": str(uuid.uuid4())})
    assert conflicting["isError"] and "different change" in conflicting["content"][0]["text"]

    path = f"/api/v1/mcp-operations/{op.id}"
    assert (await client.get(path, headers=_clerk(user, team))).status_code == 404
    assert (await client.post(path + "/confirm", headers=_clerk(user, team))).status_code == 404
    async with tenant_session(team.id) as db:
        old = await db.get(McpOperation, op.id)
        assert old.completed_at is None and old.result is None and old.confirmed_by is None
        confirmed = await db.scalar(
            select(McpActionActivity.id).where(
                McpActionActivity.operation_id == op.id,
                McpActionActivity.action == "write_confirmed",
            )
        )
        assert confirmed is None


async def test_completed_receipt_revalidates_scope_token_version_and_current_permissions(
    mcp_fixture,  # noqa: F811
    monkeypatch,
):
    from app.config import settings

    client, teams, users, boundary = mcp_fixture
    owner, peer = users
    home, second = teams
    issued, op = await _historical_operation(client, home, owner, result={"status": "in_transit"})
    secret = issued["secret"]
    expected = {
        "operation_id": str(op.id),
        "request_id": str(op.request_id),
        "action": op.action_name,
        "status": "completed",
        "result": {"status": "in_transit"},
    }
    assert (await _lookup(client, secret, op))["structuredContent"] == expected
    assert (await _replay(client, secret, op))["structuredContent"] == expected
    summaries = await _audit_summaries(client, home, owner, op)
    assert any("write requested" in summary and origin == "mcp" for summary, origin in summaries)
    assert any(
        "write confirmed" in summary and origin == "firstout" for summary, origin in summaries
    )
    assert all("write completed" not in summary for summary, _ in summaries)
    with monkeypatch.context() as patch:
        patch.setattr(settings, "mcp_writes_enabled", False)
        assert (await _lookup(client, secret, op))["structuredContent"] == expected

    for staff in (_clerk(owner, home), _clerk(peer, home), _clerk(owner, second)):
        other = (await _issue(client, staff, "Other token")).json()
        assert (await _lookup(client, other["secret"], op))["isError"]

    identity = (home.clerk_org_id, owner.clerk_user_id)
    boundary.memberships.remove(identity)
    denied = await _rpc(
        client,
        secret,
        "tools/call",
        {
            "name": "run_read",
            "arguments": {
                "action": "operations_lookup",
                "arguments": {"request_id": str(op.request_id)},
            },
        },
    )
    assert denied.status_code == 401
    boundary.memberships.add(identity)

    async with tenant_session(home.id) as db, unit_of_work(db):
        await db.execute(
            delete(RolePermission).where(
                RolePermission.team_id == home.id, RolePermission.key == STOCK_TRANSFER
            )
        )
    assert (await _lookup(client, secret, op))["isError"]
    assert (await _replay(client, secret, op))["isError"]
    async with tenant_session(home.id) as db, unit_of_work(db):
        await _grant_transfers(db, home.id)

    rotated = await client.post(
        f"/api/v1/mcp-tokens/{issued['token']['id']}/rotate",
        headers=_clerk(owner, home),
        json={"version": issued["token"]["version"]},
    )
    assert rotated.status_code == 200
    assert (await _lookup(client, rotated.json()["secret"], op))["isError"]
    assert (await _replay(client, rotated.json()["secret"], op))["isError"]
