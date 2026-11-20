"""Route actions over a real Streamable HTTP connection, as the token owner."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select, text, update

from app import mcp_server
from app.config import settings
from app.crud.mcp_operation import McpOperationCRUD
from app.database import tenant_session
from app.mcp_server import ACTIONS_URI, INSTRUCTIONS
from app.middleware.auth import mcp_actor
from app.models.mcp_operation import McpOperation
from app.models.mcp_token import McpToken
from app.models.membership import Membership
from app.models.supplier import Supplier
from app.models.team import Team
from app.models.user import User
from app.services.clerk_api import ClerkAPI
from app.services.mcp_actions import ACTIONS
from app.services.mcp_operations import begin_route_operation
from app.services.mcp_route_runner import UNKNOWN_OUTCOME, run_route
from app.services.permissions import PermissionService
from app.services.roles import RoleSeedService
from f0rge_db.crud import unit_of_work
from tests.test_mcp_tokens import ClerkBoundary, _clerk, _issue, _rpc, mcp_fixture  # noqa: F401
from tests.test_mcp_workflow import _live_connection
from tests.test_sku_archive_commit_races import isolated_requests

_MODERN = "2026-07-28"
_META = {
    "io.modelcontextprotocol/protocolVersion": _MODERN,
    "io.modelcontextprotocol/clientInfo": {"name": "staff-fixture", "version": "1"},
    "io.modelcontextprotocol/clientCapabilities": {},
}


@asynccontextmanager
async def _staff_connection(database_url, monkeypatch):
    async with isolated_requests(database_url) as (maker, ids):
        monkeypatch.setattr("app.database.async_session_maker", maker)
        monkeypatch.setattr(settings, "clerk_secret_key", "fixture-mcp-clerk-key")
        boundary = ClerkBoundary()
        async with maker() as db:
            await RoleSeedService(db).seed()
            async with unit_of_work(db):
                user = await db.get(User, ids["actor"])
                team = await db.get(Team, ids["team"])
                user.clerk_user_id, team.clerk_org_id = "user_live", "org_live"
                boundary.memberships.add((team.clerk_org_id, user.clerk_user_id))
        staff = _clerk(user, team)
        async with httpx.AsyncClient(transport=httpx.MockTransport(boundary.respond)) as http:
            provider = ClerkAPI(http, settings.clerk_secret_key)
            async with _live_connection(monkeypatch, provider) as client:
                issued = await _issue(client, staff)
                assert issued.status_code == 201, issued.text
                secret = issued.json()["secret"]

                async def rpc(method, params, *, modern=True, name=None):
                    headers = {"Mcp-Protocol-Version": _MODERN, "Mcp-Method": method}
                    if name or "uri" in params:
                        headers["Mcp-Name"] = name or params["uri"]
                    reply = await _rpc(
                        client,
                        secret,
                        method,
                        {**params, "_meta": _META} if modern else params,
                        **(headers if modern else {}),
                    )
                    assert reply.status_code == 200, reply.text
                    return reply.json()

                async def call(tool, *, expected_error=None, **args):
                    reply = await rpc("tools/call", {"name": tool, "arguments": args}, name=tool)
                    result = reply["result"]
                    if expected_error is not None:
                        assert (
                            result["isError"] and expected_error in result["content"][0]["text"]
                        ), result
                        return result["content"][0]["text"]
                    assert not result["isError"], result["content"]
                    return result["structuredContent"]

                async def set_role(role):
                    async with maker() as db, unit_of_work(db):
                        await db.execute(
                            update(Membership)
                            .where(Membership.user_id == user.id, Membership.team_id == team.id)
                            .values(role=role, is_legacy_home=False)
                        )

                async def suppliers(name):
                    async with maker() as db:
                        return await db.scalar(
                            select(func.count()).select_from(Supplier).where(Supplier.name == name)
                        )

                async def operation(request_id):
                    async with maker() as db:
                        return await db.scalar(
                            select(McpOperation).where(
                                McpOperation.request_id == uuid.UUID(request_id)
                            )
                        )

                async def events(query):
                    reply = await client.get(
                        "/api/v1/audit/events", headers=staff, params={"source": "mcp", "q": query}
                    )
                    assert reply.status_code == 200
                    return reply.json()["items"]

                yield SimpleNamespace(
                    rpc=rpc,
                    call=call,
                    set_role=set_role,
                    suppliers=suppliers,
                    operation=operation,
                    events=events,
                    maker=maker,
                    ids=ids,
                    user=user,
                    team=team,
                    token=issued.json()["token"],
                )


def _supplier(name, request_id=None):
    return {
        "action": "create_supplier",
        "arguments": {"body": {"name": name, "default_currency": "ZAR"}},
        "request_id": request_id or str(uuid.uuid4()),
    }


async def test_route_read_write_receipt_replay_and_audit(second_postgres_url, monkeypatch):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:
        assert "Books" in (await mcp.call("find_actions"))["domains"]
        found = await mcp.call("find_actions", query="create supplier")
        create = next(item for item in found["actions"] if item["name"] == "create_supplier")
        assert create["effect"] == "write" and create["tab"] == "Catalogue / Suppliers"
        assert create["inputSchema"]["required"] == ["body"]
        assert "$defs" in create["inputSchema"]

        sku = await mcp.call(
            "run_read", action="get_sku", arguments={"sku_id": str(mcp.ids["sku"])}
        )
        assert sku["our_ref"] == "RACE-EXISTING"
        listed = await mcp.call("run_read", action="list_suppliers", arguments={"archived": False})
        assert [item["name"] for item in listed["items"]] == ["Archive race supplier"]
        report = await mcp.call(
            "run_read", action="profit_loss", arguments={"from": "2026-01-01", "to": "2026-01-31"}
        )
        assert report["from_date"] == "2026-01-01"
        await mcp.call(
            "run_write", **{**_supplier("x"), "action": "get_sku"}, expected_error="runner matching"
        )
        await mcp.call(
            "run_read", action="create_supplier", arguments={}, expected_error="runner matching"
        )

        write = _supplier("Route Timber")
        first = await mcp.call("run_write", **write)
        # Only the first answer carries the route's own response.
        assert first.pop("response")["default_currency"] == "ZAR"
        receipt = first
        assert receipt["status"] == "completed" and receipt["action"] == "create_supplier"
        result = receipt["result"]
        assert result["http_status"] == 201 and result["name"] == "Route Timber"
        assert uuid.UUID(result["id"])
        # The same request ID returns the saved receipt and never runs the route again.
        assert await mcp.call("run_write", **write) == receipt
        lookup = {"request_id": write["request_id"]}
        assert await mcp.call("run_read", action="operations_lookup", arguments=lookup) == receipt
        assert await mcp.suppliers("Route Timber") == 1
        await mcp.call(
            "run_write",
            **_supplier("Another name", write["request_id"]),
            expected_error="already used for a different change",
        )
        assert await mcp.suppliers("Another name") == 0

        rows = [
            row
            for row in await mcp.events(result["id"])
            if row["operation_id"] == receipt["operation_id"]
        ]
        assert sum("write completed" in row["summary"] for row in rows) == 1
        assert any("write replayed" in row["summary"] for row in rows)
        assert {row["record_id"] for row in rows} == {result["id"]}
        assert {row["origin"] for row in rows} == {"mcp"}
        assert {row["actor"] for row in rows} == {mcp.user.email}
        assert {row["token_id"] for row in rows} == {mcp.token["id"]}
        assert any("action read · get sku" in row["summary"] for row in await mcp.events("get sku"))


async def test_route_permissions_exclusions_and_paused_writes(second_postgres_url, monkeypatch):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:

        async def visible():
            found = await mcp.call("find_actions", query="create supplier")
            index = await mcp.rpc("resources/read", {"uri": ACTIONS_URI})
            listing = index["result"]["contents"][0]["text"]
            return (
                "create_supplier" in [item["name"] for item in found["actions"]],
                "create_supplier (write)" in listing,
                listing,
            )

        assert (await visible())[:2] == (True, True)
        # Identity routes exist in the API but never in the catalogue.
        for excluded in ("create_token", "create_user", "update_role", "execute_records"):
            await mcp.call(
                "run_write",
                action=excluded,
                arguments={},
                request_id=str(uuid.uuid4()),
                expected_error="unavailable with your current access",
            )
        await mcp.call("run_read", action="list_users", arguments={}, expected_error="unavailable")

        await mcp.set_role("till")  # No catalogue.mutate.
        in_search, in_index, listing = await visible()
        assert not in_search and not in_index
        assert "get_supplier (read)" in listing and "create_till_sale (write)" in listing
        denied = _supplier("Denied Timber")
        await mcp.call("run_write", **denied, expected_error="unavailable with your current access")
        assert await mcp.operation(denied["request_id"]) is None

        # Even past MCP's own check, the route refuses with its own permission dependency.
        action = ACTIONS["create_supplier"]
        args = action.arguments.model_validate(denied["arguments"])
        with mcp_actor(mcp.user.id, mcp.team.clerk_org_id):
            outcome = await run_route(action.route, args, denied["arguments"]["body"])
        assert (outcome.status, outcome.audit) == (403, "denied")
        with monkeypatch.context() as patch:

            async def allow(self, user_id, keys):
                return True

            patch.setattr(PermissionService, "current_member_has_any", allow)
            await mcp.call(
                "run_write", **denied, expected_error="unavailable with your current access"
            )
            refused = await mcp.call(
                "run_read",
                action="operations_lookup",
                arguments={"request_id": denied["request_id"]},
            )
        assert refused["status"] == "failed" and "unavailable" in refused["message"]
        assert (await mcp.operation(denied["request_id"])).result["http_status"] == 403
        assert await mcp.suppliers("Denied Timber") == 0
        assert any(
            "write requested · create supplier · denied" in row["summary"]
            for row in await mcp.events("denied")
        )

        await mcp.set_role("owner")
        with monkeypatch.context() as patch:
            patch.setattr(settings, "mcp_writes_enabled", False)
            in_search, in_index, listing = await visible()
            assert not in_search and not in_index and "(write)" not in listing
            assert "get_supplier (read)" in listing
            await mcp.call("run_write", **_supplier("Paused Timber"), expected_error="paused")
        assert await mcp.suppliers("Paused Timber") == 0


async def test_route_refusals_are_reported_and_saved_as_failed(second_postgres_url, monkeypatch):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:
        invalid = await mcp.call(
            "run_write",
            action="create_supplier",
            arguments={"body": {"default_currency": "private-value"}},
            request_id=str(uuid.uuid4()),
            expected_error="Invalid arguments",
        )
        assert "body.name (missing)" in invalid and "private-value" not in invalid
        await mcp.call(
            "run_read",
            action="get_sku",
            arguments={"sku_id": "../suppliers"},
            expected_error="sku_id (uuid_parsing)",
        )
        missing = await mcp.call(
            "run_read",
            action="get_sku",
            arguments={"sku_id": str(uuid.uuid4())},
            expected_error="not found",
        )
        assert "SKU" in missing

        duplicate = _supplier("Archive race supplier")
        message = "A supplier with this name already exists"
        refused = await mcp.call("run_write", **duplicate, expected_error=message)
        assert refused.endswith(": " + message)
        saved = await mcp.operation(duplicate["request_id"])
        assert saved.completed_at is None
        assert saved.result == {"state": "failed", "http_status": 409, "message": message}
        # The request ID is spent. A replay reports the refusal and changes nothing.
        replay = await mcp.call("run_write", **duplicate)
        assert replay["status"] == "failed" and replay["message"].startswith(message)
        assert "new request ID" in replay["message"]
        lookup = {"request_id": duplicate["request_id"]}
        assert await mcp.call("run_read", action="operations_lookup", arguments=lookup) == replay
        assert await mcp.suppliers("Archive race supplier") == 1
        assert any(
            "write requested · create supplier · failed" in row["summary"]
            for row in await mcp.events("failed")
        )


async def test_unrecorded_outcome_is_unknown_and_never_runs_twice(second_postgres_url, monkeypatch):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:
        lost = _supplier("Lost Receipt Timber")
        with monkeypatch.context() as patch:

            async def crash(*args, **kwargs):
                raise RuntimeError("connection lost with password hunter2")

            patch.setattr(mcp_server, "finish_route_operation", crash)
            error = await mcp.call("run_write", **lost, expected_error=UNKNOWN_OUTCOME)
        assert "hunter2" not in error
        # The route committed its change, but MCP cannot know that.
        assert await mcp.suppliers("Lost Receipt Timber") == 1
        replay = await mcp.call("run_write", **lost)
        assert replay["status"] == "unknown" and "new request ID" in replay["message"]
        lookup = {"request_id": lost["request_id"]}
        assert await mcp.call("run_read", action="operations_lookup", arguments=lookup) == replay
        assert await mcp.suppliers("Lost Receipt Timber") == 1

        # If two calls ever passed the token lock together, the unique request still decides.
        action = ACTIONS["create_supplier"]
        args = action.arguments.model_validate(lost["arguments"])
        real_lookup, misses = McpOperationCRUD.by_request, [None]

        async def miss_once(self, token, request_id):
            return misses.pop() if misses else await real_lookup(self, token, request_id)

        async with mcp.maker() as db, unit_of_work(db):
            token = await db.get(McpToken, uuid.UUID(mcp.token["id"]))
            with monkeypatch.context() as patch:
                patch.setattr(McpOperationCRUD, "by_request", miss_once)
                raced = await begin_route_operation(
                    db, token, action, args, uuid.UUID(lost["request_id"])
                )
        assert raced["status"] == "unknown" and misses == []

        failing = _supplier("Server Error Timber")
        with monkeypatch.context() as patch:

            async def explode(self, *args, **kwargs):
                raise RuntimeError("database password is hunter2")

            patch.setattr("app.services.suppliers.SupplierService.create", explode)
            error = await mcp.call("run_write", **failing, expected_error=UNKNOWN_OUTCOME)
            assert "hunter2" not in error
        assert (await mcp.call("run_write", **failing))["status"] == "unknown"
        assert await mcp.suppliers("Server Error Timber") == 0


async def test_same_request_id_in_parallel_makes_one_record_and_holds_no_lock(
    second_postgres_url, monkeypatch
):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:
        real, runs, check_locks = mcp_server.run_route, [], True

        async def counted(route, args, body):
            if check_locks:
                # The route works on its own connection and may need these rows. MCP's
                # authorising transaction locked them, so it must have committed by now.
                async with mcp.maker() as other:
                    await other.execute(text("SELECT id FROM mcp_tokens FOR UPDATE NOWAIT"))
                    await other.execute(text("SELECT id FROM teams FOR UPDATE NOWAIT"))
                    await other.rollback()
            runs.append(route.path)
            return await real(route, args, body)

        monkeypatch.setattr(mcp_server, "run_route", counted)
        alone = await mcp.call("run_write", **_supplier("Unlocked Timber"))
        assert alone["status"] == "completed" and runs.pop() == "/api/v1/suppliers"

        check_locks = False  # A parallel caller briefly holds the token row to authenticate.
        write = _supplier("Parallel Timber")
        first, second = await asyncio.gather(
            mcp.call("run_write", **write), mcp.call("run_write", **write)
        )
        # The loser sees the started receipt, or the finished one if it arrived late.
        assert {first["status"], second["status"]} <= {"completed", "unknown"}
        assert "completed" in {first["status"], second["status"]}
        assert runs == ["/api/v1/suppliers"]
        assert await mcp.suppliers("Parallel Timber") == 1
        settled = await mcp.call(
            "run_read", action="operations_lookup", arguments={"request_id": write["request_id"]}
        )
        assert settled["status"] == "completed"


@pytest.mark.parametrize("modern", [True, False])
async def test_instructions_and_actions_resource_on_both_protocols(
    second_postgres_url, monkeypatch, modern
):
    async with _staff_connection(second_postgres_url, monkeypatch) as mcp:
        if modern:
            hello = await mcp.rpc("server/discover", {})
        else:
            hello = await mcp.rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "fixture", "version": "1"},
                },
                modern=False,
            )
        assert hello["result"]["instructions"] == INSTRUCTIONS and len(INSTRUCTIONS) < 1200
        for word in ("find_actions", "run_read", "run_write", "operations_lookup", ACTIONS_URI):
            assert word in INSTRUCTIONS

        listed = await mcp.rpc("resources/list", {}, modern=modern)
        assert [item["uri"] for item in listed["result"]["resources"]] == [ACTIONS_URI]
        read = await mcp.rpc("resources/read", {"uri": ACTIONS_URI}, modern=modern)
        (content,) = read["result"]["contents"]
        assert content["mimeType"] == "text/plain"
        assert "\n## Warehouse / Transfers\n" in content["text"]
        assert "\ntransfers_create_draft (write): " in content["text"]
        assert "\ncreate_supplier (write): " in content["text"]
        assert "create_token" not in content["text"] and "inputSchema" not in content["text"]
        assert any("actions found" in row["summary"] for row in await mcp.events("actions found"))


async def test_route_actions_stay_inside_the_token_business(mcp_fixture):  # noqa: F811
    """On the migrated schema, with one person who belongs to two businesses."""
    client, teams, users, _boundary = mcp_fixture
    secret = (await _issue(client, _clerk(users[0], teams[0]))).json()["secret"]

    async def call(tool, **args):
        reply = await _rpc(client, secret, "tools/call", {"name": tool, "arguments": args})
        result = reply.json()["result"]
        assert not result["isError"], result["content"]
        return result["structuredContent"]

    # The same person belongs to both businesses. The token reaches only its own.
    skus = await call("run_read", action="list_skus", arguments={})
    assert [item["name"] for item in skus["items"]] == ["Catalogue Fixture 0"]
    # This role holds no write permission. The API opens the preview to all staff.
    request_id = str(uuid.uuid4())
    preview = await call(
        "run_write", action="preview_auto_match", arguments={}, request_id=request_id
    )
    assert preview["status"] == "completed" and preview["result"]["http_status"] == 200
    replay = await call(
        "run_write", action="preview_auto_match", arguments={}, request_id=request_id
    )
    assert replay == {key: value for key, value in preview.items() if key != "response"}
    async with tenant_session(teams[0].id) as db:
        owners = (
            await db.scalars(
                select(McpOperation.team_id).where(
                    McpOperation.team_id.in_([team.id for team in teams])
                )
            )
        ).all()
    assert owners == [teams[0].id]
