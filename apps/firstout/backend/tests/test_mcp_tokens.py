from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.config import settings
from app.database import tenant_session
from app.main import app
from app.mcp_server import create_mcp_app
from app.models.mcp_token import McpToken
from app.models.membership import Membership
from app.models.role import Role, RolePermission
from app.models.sku import Sku
from app.models.team import Team
from app.models.user import User
from app.permissions import STOCK_COST_VIEW
from app.services.clerk_api import ClerkAPI
from f0rge_db.crud import unit_of_work
from tests.conftest import signed_clerk_token

_TOKENS = "/api/v1/mcp-tokens"


def _bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def _clerk(user: User, team: Team) -> dict[str, str]:
    return _bearer(
        signed_clerk_token(user.clerk_user_id, org_id=team.clerk_org_id, org_slug=team.slug)
    )


class ClerkBoundary:
    def __init__(self) -> None:
        self.unavailable = False
        self.restrictions: dict[str, dict[str, bool]] = {}
        self.memberships: set[tuple[str, str]] = set()

    def respond(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer fixture-mcp-clerk-key"
        if self.unavailable:
            return httpx.Response(503)
        if request.url.path.startswith("/v1/users/"):
            subject = request.url.path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={
                    "id": subject,
                    "banned": False,
                    "locked": False,
                    **self.restrictions.get(subject, {}),
                },
            )
        prefix, organisation, route = request.url.path.split("/")[2:]
        assert (prefix, route) == ("organizations", "memberships")
        subject = request.url.params["user_id"]
        members = (
            [{"public_user_data": {"user_id": subject}}]
            if (organisation, subject) in self.memberships
            else []
        )
        return httpx.Response(200, json={"data": members})


@pytest.fixture
async def mcp_fixture(monkeypatch):
    monkeypatch.setattr(settings, "mcp_public_url", "http://localhost:8003/mcp")
    monkeypatch.setattr(settings, "clerk_secret_key", "fixture-mcp-clerk-key")
    boundary = ClerkBoundary()
    # One person in two organisations plus a second staff member in the first.
    stamp = uuid.uuid4().hex
    teams = [
        Team(name=f"MCP test {i}", slug=f"mcp-{i}-{stamp}", clerk_org_id=f"org_{i}_{stamp}")
        for i in range(2)
    ]
    users = [
        User(
            email=f"mcp-{i}-{stamp}@example.com",
            clerk_user_id=f"user_{i}_{stamp}",
            password_hash="!clerk-only",
            role="reader",
        )
        for i in range(2)
    ]
    async with tenant_session() as db, unit_of_work(db):
        db.add_all(teams)
        await db.flush()
        for user in users:
            user.team_id = teams[0].id
        db.add_all(users)
        await db.flush()
        db.add_all(
            Membership(user_id=user.id, team_id=team.id, role="reader", is_legacy_home=index == 0)
            for index, team in enumerate(teams)
            for user in (users if index == 0 else users[:1])
        )
    for index, team in enumerate(teams):
        boundary.memberships.update(
            (team.clerk_org_id, user.clerk_user_id) for user in (users if index == 0 else users[:1])
        )
        async with tenant_session(team.id) as db, unit_of_work(db):
            role = Role(slug="reader", name="Reader")
            db.add(role)
            await db.flush()
            db.add(RolePermission(role_id=role.id, key=STOCK_COST_VIEW))
            db.add(
                Sku(
                    our_ref=f"{index}-{stamp}",
                    our_barcode=f"b{index}-{stamp}",
                    name=f"Catalogue Fixture {index}",
                    design=f"fixture-{stamp}",
                    fabric=f"{index}",
                )
            )
    async with httpx.AsyncClient(transport=httpx.MockTransport(boundary.respond)) as provider_http:
        mcp_app = create_mcp_app(ClerkAPI(provider_http, settings.clerk_secret_key))
        monkeypatch.setattr(app.state, "firstout_mcp", mcp_app, raising=False)
        started, stop = asyncio.Event(), asyncio.Event()

        async def run_lifespan():
            async with mcp_app.router.lifespan_context(mcp_app):
                started.set()
                await stop.wait()

        lifespan_task = asyncio.create_task(run_lifespan())
        await started.wait()
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost:8003"
            ) as client:
                yield client, teams, users, boundary
        finally:
            stop.set()
            await lifespan_task
    async with tenant_session() as db, unit_of_work(db):
        await db.execute(delete(Sku).where(Sku.team_id.in_([team.id for team in teams])))
        await db.execute(delete(Role).where(Role.team_id.in_([team.id for team in teams])))
        await db.execute(
            delete(Membership).where(Membership.user_id.in_([user.id for user in users]))
        )
        await db.execute(delete(User).where(User.id.in_([user.id for user in users])))
        await db.execute(delete(Team).where(Team.id.in_([team.id for team in teams])))


async def _rpc(client, token: str, method: str, params=None, **extra_headers):
    return await client.post(
        "/mcp",
        headers={
            "Accept": "application/json, text/event-stream",
            **_bearer(token),
            **extra_headers,
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


async def _issue(client, headers, name="Work laptop", days=30):
    return await client.post(_TOKENS, headers=headers, json={"name": name, "expires_in_days": days})


async def test_token_lifecycle_secret_isolation_mcp_audit_and_current_permissions(mcp_fixture):
    client, teams, users, _boundary = mcp_fixture
    original_staff = _clerk(users[0], teams[0])
    other_staff = _clerk(users[1], teams[0])
    another_business = _clerk(users[0], teams[1])
    assert (await client.get(_TOKENS)).status_code == 401
    assert (await _issue(client, original_staff, "  ")).status_code == 422
    assert (await _issue(client, original_staff, "Desk", days=8)).status_code == 422
    result = await _issue(client, original_staff, "  Work laptop  ")
    assert result.status_code == 201
    assert result.headers["Cache-Control"] == "no-store"
    personal = result.json()
    issued = personal["token"]
    secret = personal["secret"]
    assert issued["name"] == "Work laptop"
    assert issued["status"] == "active"
    assert issued["suffix"] == secret[-4:]
    assert issued["last_used_at"] is None
    assert datetime.fromisoformat(issued["expires_at"]) - datetime.now(UTC) > timedelta(days=29)
    path = f"{_TOKENS}/{issued['id']}"

    async with tenant_session(teams[0].id) as db:
        stored_digest = await db.scalar(
            select(McpToken.digest).where(McpToken.id == uuid.UUID(issued["id"]))
        )
        assert len(stored_digest) == 64 and secret not in stored_digest

    for wrong_scope in (other_staff, another_business):
        result = await client.get(_TOKENS, headers=wrong_scope)
        assert result.json()["tokens"] == result.json()["activity"] == []
        assert (await client.delete(path, headers=wrong_scope)).status_code == 404
        result = await client.post(f"{path}/rotate", headers=wrong_scope, json={"version": 1})
        assert result.status_code == 404
    assert (await client.get(_TOKENS, headers=_bearer(secret))).status_code in {401, 403}
    assert (await _rpc(client, original_staff["Authorization"][7:], "ping")).status_code == 401
    assert (await _rpc(client, secret, "ping", Origin="https://example.org")).status_code == 403
    assert (await _rpc(client, secret, "ping", Host="example.org")).status_code == 421

    initialize = await _rpc(
        client,
        secret,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "fixture", "version": "1"},
        },
    )
    assert initialize.json()["result"]["serverInfo"]["name"] == "Firstout"
    protocol = "2026-07-28"
    discovery = await _rpc(
        client,
        secret,
        "server/discover",
        {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": protocol,
                "io.modelcontextprotocol/clientInfo": {"name": "Fixture", "version": "1"},
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
        **{"Mcp-Protocol-Version": protocol, "Mcp-Method": "server/discover"},
    )
    assert discovery.status_code == 200
    assert protocol in discovery.json()["result"]["supportedVersions"]
    tools = await _rpc(client, secret, "tools/list")
    assert {tool["name"] for tool in tools.json()["result"]["tools"]} == {
        "catalogue_search",
        "find_actions",
        "run_read",
        "request_write",
    }
    args = {
        "name": "catalogue_search",
        "arguments": {"query": "Catalogue Fixture", "include_unit_cost": True},
    }
    read = await _rpc(client, secret, "tools/call", args)
    assert read.json()["result"]["structuredContent"]["total"] == 1
    assert read.json()["result"]["structuredContent"]["items"][0]["name"] == "Catalogue Fixture 0"
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(delete(RolePermission).where(RolePermission.team_id == teams[0].id))
    denied = await _rpc(client, secret, "tools/call", args)
    assert denied.json()["result"]["isError"] is True
    args["arguments"]["include_unit_cost"] = False
    assert (await _rpc(client, secret, "tools/call", args)).json()["result"]["isError"] is False

    result = await client.get(_TOKENS, headers=original_staff)
    assert secret not in result.text and stored_digest not in result.text
    assert result.json()["tokens"][0]["last_used_at"] is not None
    assert result.json()["endpoint"] == "http://localhost:8003/mcp"
    assert [(row["source"], row["result"]) for row in result.json()["activity"]] == [
        ("mcp", "success"),
        ("mcp", "denied"),
        ("mcp", "success"),
        ("firstout", "success"),
    ]
    replacement = await client.post(f"{path}/rotate", headers=original_staff, json={"version": 1})
    assert replacement.status_code == 200
    assert replacement.headers["Cache-Control"] == "no-store"
    rotated = replacement.json()
    assert rotated["token"]["version"] == 2
    assert rotated["token"]["expires_at"] == issued["expires_at"]
    assert rotated["token"]["last_used_at"] is None
    assert (await _rpc(client, secret, "tools/list")).status_code == 401
    assert (await _rpc(client, rotated["secret"], "tools/list")).status_code == 200
    assert (await client.delete(path, headers=original_staff)).status_code == 204
    assert (await client.delete(path, headers=original_staff)).status_code == 204
    assert (await _rpc(client, rotated["secret"], "tools/list")).status_code == 401
    result = (await client.get(_TOKENS, headers=original_staff)).json()
    assert result["tokens"][0]["status"] == "revoked"
    assert [event["action"] for event in result["activity"][:2]] == ["revoked", "rotated"]


async def test_duplicate_and_stale_rotations_have_one_winner(mcp_fixture):
    client, teams, users, _boundary = mcp_fixture
    staff = _clerk(users[0], teams[0])
    creates = await asyncio.gather(
        _issue(client, staff, "Work laptop"), _issue(client, staff, "WORK LAPTOP")
    )
    assert sorted(item.status_code for item in creates) == [201, 409]
    issued = next(item.json()["token"] for item in creates if item.status_code == 201)
    path = f"{_TOKENS}/{issued['id']}/rotate"
    rotations = await asyncio.gather(
        *[client.post(path, headers=staff, json={"version": issued["version"]}) for _ in range(2)]
    )
    assert sorted(item.status_code for item in rotations) == [200, 409]
    current_secret = next(item.json()["secret"] for item in rotations if item.status_code == 200)
    assert (await _rpc(client, current_secret, "tools/list")).status_code == 200


async def test_disabled_or_expired_credential_is_rejected(mcp_fixture):
    client, teams, users, _boundary = mcp_fixture
    staff = _clerk(users[0], teams[0])
    expired = (await _issue(client, staff, "Expires soon", days=7)).json()
    current = (await _issue(client, staff, "Keep", days=90)).json()
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(
            update(McpToken)
            .where(McpToken.id == uuid.UUID(expired["token"]["id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=5))
        )
    assert (await _rpc(client, expired["secret"], "tools/list")).status_code == 401
    result = (await client.get(_TOKENS, headers=staff)).json()
    assert sorted(row["status"] for row in result["tokens"]) == ["active", "expired"]
    async with tenant_session(teams[0].id) as db, unit_of_work(db):
        await db.execute(
            update(Membership)
            .where(Membership.user_id == users[0].id, Membership.team_id == teams[0].id)
            .values(is_disabled=True)
        )
    assert (await _rpc(client, current["secret"], "tools/list")).status_code == 401
    assert (await client.get(_TOKENS, headers=staff)).status_code == 401


async def test_clerk_removal_blocks_legacy_home_token_without_changing_local_grant(mcp_fixture):
    client, teams, users, boundary = mcp_fixture
    staff = _clerk(users[0], teams[0])
    token = (await _issue(client, staff)).json()["secret"]
    assert (await _rpc(client, token, "tools/list")).status_code == 200

    subject = users[0].clerk_user_id
    clerk_membership = (teams[0].clerk_org_id, subject)
    boundary.memberships.remove(clerk_membership)
    assert (await _rpc(client, token, "tools/list")).status_code == 401
    async with tenant_session(teams[0].id) as db:
        member = await db.scalar(
            select(Membership).where(
                Membership.user_id == users[0].id,
                Membership.team_id == teams[0].id,
            )
        )
        assert member.is_legacy_home and not member.is_disabled

    boundary.memberships.add(clerk_membership)
    for restriction in ("banned", "locked", "deprovisioned"):
        boundary.restrictions[subject] = {restriction: True}
        assert (await _rpc(client, token, "tools/list")).status_code == 401
    boundary.restrictions.clear()
    boundary.unavailable = True
    assert (await _rpc(client, token, "tools/list")).status_code == 503


async def test_token_issuance_requires_clerk_server_key(mcp_fixture, monkeypatch):
    client, teams, users, _boundary = mcp_fixture
    monkeypatch.setattr(settings, "clerk_secret_key", "")
    result = await _issue(client, _clerk(users[0], teams[0]))
    assert result.status_code == 503
    assert "secret" not in result.json()


async def test_discovery_paging_and_runners_follow_current_membership(mcp_fixture, monkeypatch):
    client, teams, users, _ = mcp_fixture
    team = teams[0]
    issued = await _issue(client, _clerk(users[0], team))
    secret = issued.json()["secret"]

    async def call(tool, **args):
        response = await _rpc(client, secret, "tools/call", {"name": tool, "arguments": args})
        return response.json()["result"]

    domains = (await call("find_actions"))["structuredContent"]["domains"]
    assert set(domains) == {
        "Home",
        "Catalogue",
        "Stock",
        "Warehouse",
        "Sales",
        "Books",
        "Admin",
    }
    first = (await call("find_actions", tab="Warehouse"))["structuredContent"]
    assert len(first["actions"]) == 3 and first["next_offset"] == 3
    second = (await call("find_actions", tab="Warehouse", offset=3))["structuredContent"]
    assert {a["name"] for a in first["actions"]}.isdisjoint(a["name"] for a in second["actions"])

    async def discover():
        return (await call("find_actions", query="draft quote", tab="Sales"))["structuredContent"][
            "actions"
        ]

    name = "quotes_create_draft"
    assert name not in {action["name"] for action in await discover()}
    request = dict(action=name, request_id=str(uuid.uuid4()), arguments={})
    assert (await call("request_write", **request))["isError"]
    async with tenant_session(team.id) as db, unit_of_work(db):
        role_id = await db.scalar(
            select(Role.id).where(Role.team_id == team.id, Role.slug == "reader")
        )
        db.add(RolePermission(role_id=role_id, key="sales.quotes"))
    assert name in {action["name"] for action in await discover()}
    wrong_runner = await call("run_read", action=name, arguments={})
    assert wrong_runner["isError"] and "runner" in wrong_runner["content"][0]["text"]
    invalid = await call("request_write", **request)
    assert invalid["isError"] and "Invalid arguments" in invalid["content"][0]["text"]

    monkeypatch.setattr(settings, "mcp_writes_enabled", False)
    assert name not in {action["name"] for action in await discover()}
    paused = await call("request_write", **request)
    assert paused["isError"] and "paused" in paused["content"][0]["text"]
    assert not (await call("run_read", action="catalogue_search", arguments={"query": "Fixture"}))[
        "isError"
    ]
    monkeypatch.setattr(settings, "mcp_writes_enabled", True)
    async with tenant_session(team.id) as db, unit_of_work(db):
        await db.execute(delete(RolePermission).where(RolePermission.team_id == team.id))
    denied = await call("request_write", **request)
    assert denied["isError"] and "unavailable" in denied["content"][0]["text"]
    history = (await client.get(_TOKENS, headers=_clerk(users[0], team))).json()["activity"]
    assert history[0]["action_name"] == name and history[0]["result"] == "denied"
