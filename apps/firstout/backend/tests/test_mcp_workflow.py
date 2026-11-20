"""Exercise a real Streamable HTTP connection with a disposable database and synthetic Clerk."""

from __future__ import annotations

import asyncio
import datetime
import socket
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import httpx
import uvicorn
from sqlalchemy import select, update

from app.config import settings
from app.main import app
from app.mcp_server import create_mcp_app
from app.models.account import Account
from app.models.location import Location
from app.models.membership import Membership
from app.models.mcp_operation import McpOperation
from app.models.team import Team
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User
from app.services.clerk_api import ClerkAPI
from app.services.locations import LocationSeedService
from app.services.roles import RoleSeedService
from app.services.stock_movements import StockMovementService
from f0rge_db.crud import unit_of_work
from tests.test_mcp_tokens import ClerkBoundary, _clerk, _issue, _rpc
from tests.test_sku_archive_commit_races import isolated_requests


@asynccontextmanager
async def _live_connection(monkeypatch, provider):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        monkeypatch.setattr(settings, "mcp_public_url", "http://localhost:8003/mcp")
        mcp = create_mcp_app(provider)
        monkeypatch.setattr(app.state, "firstout_mcp", mcp, raising=False)
        server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="warning"))
        async with mcp.router.lifespan_context(mcp):
            running = asyncio.create_task(server.serve(sockets=[listener]))
            try:
                async with asyncio.timeout(8):
                    while not server.started:
                        if running.done():
                            await running
                            raise RuntimeError("Test server stopped before startup")
                        await asyncio.sleep(0.02)
                async with httpx.AsyncClient(
                    base_url=origin, headers={"Host": "localhost:8003"}, trust_env=False
                ) as client:
                    yield client
            finally:
                server.should_exit = True
                await running


async def test_personal_token_domain_workflow(second_postgres_url, monkeypatch):
    async with isolated_requests(second_postgres_url) as (maker, ids):
        monkeypatch.setattr("app.database.async_session_maker", maker)
        monkeypatch.setattr(settings, "clerk_secret_key", "fixture-mcp-clerk-key")
        boundary = ClerkBoundary()
        async with maker() as db:
            await LocationSeedService(db).seed_if_empty()
            await RoleSeedService(db).seed()
            async with unit_of_work(db):
                user = await db.get(User, ids["actor"])
                team = await db.get(Team, ids["team"])
                user.clerk_user_id, team.clerk_org_id = "user_live", "org_live"
                boundary.memberships.add((team.clerk_org_id, user.clerk_user_id))
                source, dest = (await db.scalars(select(Location.id).order_by(Location.id))).all()
                accounts = (await db.scalars(select(Account.id).limit(2))).all()
                await StockMovementService(db).apply_incoming_qty(
                    ids["sku"],
                    source,
                    Decimal("2"),
                    Decimal("40"),
                    user.id,
                    UnitCostAuditSource.RECEIVE,
                    "Test opening stock",
                    record_audit=False,
                )
        staff = _clerk(user, team)
        async with httpx.AsyncClient(transport=httpx.MockTransport(boundary.respond)) as http:
            provider = ClerkAPI(http, settings.clerk_secret_key)
            async with _live_connection(monkeypatch, provider) as client:
                issued = await _issue(client, staff)
                assert issued.status_code == 201, issued.text
                secret = issued.json()["secret"]

                async def call(tool, *, expected_error=None, **args):
                    reply = await _rpc(
                        client,
                        secret,
                        "tools/call",
                        {
                            "name": tool,
                            "arguments": args,
                            "_meta": {
                                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                                "io.modelcontextprotocol/clientInfo": {
                                    "name": "staff-fixture",
                                    "version": "1",
                                },
                                "io.modelcontextprotocol/clientCapabilities": {},
                            },
                        },
                        **{
                            "Mcp-Protocol-Version": "2026-07-28",
                            "Mcp-Method": "tools/call",
                            "Mcp-Name": tool,
                        },
                    )
                    result = reply.json()["result"]
                    if expected_error is not None:
                        assert (
                            result["isError"] and expected_error in result["content"][0]["text"]
                        ), result
                        return
                    assert not result["isError"], result["content"]
                    return result["structuredContent"]

                matches = await call("find_actions", query="draft transfer", tab="Warehouse")
                assert 1 <= len(matches["actions"]) <= 3
                assert "transfers_create_draft" in {item["name"] for item in matches["actions"]}
                read = await call(
                    "run_read", action="stock_on_hand", arguments={"sku_id": str(ids["sku"])}
                )
                assert read["items"][0]["location_id"] == str(source)

                request_id = str(uuid.uuid4())
                write = {
                    "action": "transfers_create_draft",
                    "request_id": request_id,
                    "arguments": {
                        "from_location_id": str(source),
                        "to_location_id": str(dest),
                        "lines": [
                            {"sku_id": str(ids["sku"]), "qty": "1"},
                            {"sku_id": str(ids["sku"]), "qty": "1"},
                        ],
                    },
                }
                original, replay = await asyncio.gather(
                    call("run_write", **write), call("run_write", **write)
                )
                assert original == replay and original["result"]["status"] == "draft"
                transfer_id = original["result"]["transfer_id"]
                record = await call(
                    "run_read", action="transfers_get", arguments={"transfer_id": transfer_id}
                )

                async def set_role(role):
                    async with maker() as db, unit_of_work(db):
                        await db.execute(
                            update(Membership)
                            .where(Membership.user_id == user.id, Membership.team_id == team.id)
                            .values(role=role, is_legacy_home=False)
                        )

                async def balances():
                    response = await call(
                        "run_read", action="stock_on_hand", arguments={"sku_id": str(ids["sku"])}
                    )
                    return {
                        row["location_id"]: Decimal(row["on_hand"]) for row in response["items"]
                    }

                args = {"transfer_id": transfer_id}
                # This request used to require approval. Replaying it on an upgraded
                # server must never move even a fully valid, ready-to-dispatch transfer.
                old_id = uuid.uuid4()
                async with maker() as db, unit_of_work(db):
                    db.add(
                        McpOperation(
                            team_id=team.id,
                            user_id=user.id,
                            token_id=uuid.UUID(issued.json()["token"]["id"]),
                            token_version=issued.json()["token"]["version"],
                            request_id=old_id,
                            action_name="transfers_dispatch",
                            arguments=args,
                            preview={"transfer_id": transfer_id},
                            expires_at=datetime.datetime.now(datetime.UTC)
                            + datetime.timedelta(minutes=10),
                        )
                    )
                legacy = await call(
                    "run_write", action="transfers_dispatch", arguments=args, request_id=str(old_id)
                )
                assert legacy["status"] == "not_executed" and "review_url" not in legacy
                assert await balances() == {str(source): Decimal("2")}

                dispatch = {
                    "action": "transfers_dispatch",
                    "arguments": args,
                    "request_id": str(uuid.uuid4()),
                }
                await set_role("till")  # May receive but cannot dispatch.
                await call("run_write", **dispatch, expected_error="unavailable")
                await set_role("owner")
                with monkeypatch.context() as patch:
                    patch.setattr(settings, "mcp_writes_enabled", False)
                    await call("run_write", **dispatch, expected_error="paused")
                    assert await balances() == {str(source): Decimal("2")}
                shipped, replay = await asyncio.gather(
                    call("run_write", **dispatch), call("run_write", **dispatch)
                )
                assert shipped == replay
                assert (
                    shipped["status"] == "completed" and shipped["result"]["status"] == "in_transit"
                )
                assert "review_url" not in shipped
                assert await balances() == {str(source): Decimal("0")}

                await set_role("till")
                receive_id = str(uuid.uuid4())
                first_line, second_line = record["lines"]

                async def receive(second_quantity, *, expected_error=None):
                    return await call(
                        "run_write",
                        action="transfers_receive",
                        request_id=receive_id,
                        arguments={
                            **args,
                            "lines": [
                                {"line_id": first_line["line_id"], "qty_received": "1"},
                                {
                                    "line_id": second_line["line_id"],
                                    "qty_received": second_quantity,
                                },
                            ],
                        },
                        expected_error=expected_error,
                    )

                # The native service stages the first line before validating the second.
                # The failed write must roll back both the destination movement and line receipt.
                await receive("0.75", expected_error="qty")
                failed_transfer = await call("run_read", action="transfers_get", arguments=args)
                assert failed_transfer["status"] == "in_transit"
                assert all(line["qty_received"] is None for line in failed_transfer["lines"])
                assert await balances() == {str(source): Decimal("0")}
                delivered = await receive("1")
                assert (
                    delivered["status"] == "completed"
                    and delivered["result"]["status"] == "received"
                )
                assert await receive("1") == delivered
                assert (
                    await call(
                        "run_read", action="operations_lookup", arguments={"request_id": receive_id}
                    )
                    == delivered
                )
                await set_role("owner")
                stock = await call(
                    "run_read", action="stock_on_hand", arguments={"sku_id": str(ids["sku"])}
                )
                assert {row["location_id"]: Decimal(row["on_hand"]) for row in stock["items"]} == {
                    str(source): 0,
                    str(dest): 2,
                }
                for action, payload in (
                    (
                        "quotes_create_draft",
                        {
                            "customer_id": str(ids["customer"]),
                            "lines": [{"sku_id": str(ids["sku"]), "qty": 1}],
                        },
                    ),
                    (
                        "journals_create_draft",
                        {
                            "entry_date": str(datetime.date.today()),
                            "lines": [
                                {"account_id": str(accounts[0]), "debit_zar": "5"},
                                {"account_id": str(accounts[1]), "credit_zar": "5"},
                            ],
                        },
                    ),
                ):
                    intent = str(uuid.uuid4())
                    draft = await call(
                        "run_write", action=action, arguments=payload, request_id=intent
                    )
                    assert draft["result"]["number"] and draft["result"]["status"] == "draft"
                    assert (
                        await call(
                            "run_read", action="operations_lookup", arguments={"request_id": intent}
                        )
                        == draft
                    )
                events = await client.get(
                    "/api/v1/audit/events",
                    headers=staff,
                    params={"source": "mcp", "q": transfer_id},
                )
                assert events.status_code == 200
                transfer_operations = {op["operation_id"] for op in (original, shipped, delivered)}
                rows = [
                    row
                    for row in events.json()["items"]
                    if row["operation_id"] in transfer_operations
                ]
                assert {row["operation_id"] for row in rows} == transfer_operations
                assert {row["record_id"] for row in rows} == {transfer_id}
                assert {row["origin"] for row in rows} == {"mcp"}
                assert {row["actor"] for row in rows} == {user.email}
                assert {row["token_id"] for row in rows} == {issued.json()["token"]["id"]}
                for op_id in transfer_operations:
                    summaries = [row["summary"] for row in rows if row["operation_id"] == op_id]
                    assert sum("write completed" in summary for summary in summaries) == 1
                    assert any("write replayed" in summary for summary in summaries)

                failed = await client.get(
                    "/api/v1/audit/events", headers=staff, params={"source": "mcp", "q": "denied"}
                )
                assert failed.status_code == 200
                assert any(
                    "write requested" in row["summary"] and "transfers dispatch" in row["summary"]
                    for row in failed.json()["items"]
                )
