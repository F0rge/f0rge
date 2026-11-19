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
from sqlalchemy import select

from app.config import settings
from app.dependencies.tenant_signup import get_clerk_api
from app.main import app
from app.mcp_server import create_mcp_app
from app.models.account import Account
from app.models.location import Location
from app.models.team import Team
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User
from app.services.clerk_api import ClerkAPI
from app.services.locations import LocationSeedService
from app.services.stock_movements import StockMovementService
from f0rge_db.crud import unit_of_work
from tests.test_mcp_tokens import ClerkBoundary, _bearer, _clerk, _issue, _rpc
from tests.test_sku_archive_commit_races import isolated_requests


@asynccontextmanager
async def _live_connection(monkeypatch, provider):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        monkeypatch.setattr(settings, "mcp_public_url", "http://localhost:8003/mcp")
        mcp = create_mcp_app(provider)
        monkeypatch.setattr(app.state, "firstout_mcp", mcp, raising=False)
        monkeypatch.setitem(app.dependency_overrides, get_clerk_api, lambda: provider)
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

                async def call(tool, **args):
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
                        "lines": [{"sku_id": str(ids["sku"]), "qty": "2"}],
                    },
                }
                original, replay = await asyncio.gather(
                    call("request_write", **write), call("request_write", **write)
                )
                assert original == replay and original["result"]["status"] == "draft"
                transfer_id = original["result"]["transfer_id"]
                record = await call(
                    "run_read", action="transfers_get", arguments={"transfer_id": transfer_id}
                )
                args = {"transfer_id": transfer_id}
                for name, expected, payload in (
                    ("transfers_dispatch", "in_transit", args),
                    (
                        "transfers_receive",
                        "received",
                        {
                            **args,
                            "lines": [
                                {"line_id": record["lines"][0]["line_id"], "qty_received": "2"}
                            ],
                        },
                    ),
                ):
                    intent = str(uuid.uuid4())
                    pending = await call(
                        "request_write", action=name, arguments=payload, request_id=intent
                    )
                    assert pending["status"] == "awaiting_confirmation"
                    path = "/api/v1/mcp-operations/" + pending["operation_id"]
                    assert (
                        await client.post(path + "/confirm", headers=_bearer(secret))
                    ).status_code in {401, 403}
                    review = await client.get(path, headers=staff)
                    assert (
                        review.status_code == 200
                        and review.json()["preview"]["lines"][0]["quantity"] == "2"
                    )
                    confirm = await client.post(path + "/confirm", headers=staff)
                    assert confirm.status_code == 200, confirm.text
                    result = await call(
                        "run_read", action="operations_lookup", arguments={"request_id": intent}
                    )
                    assert result["result"]["status"] == expected
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
                        "request_write", action=action, arguments=payload, request_id=intent
                    )
                    assert draft["result"]["number"] and draft["result"]["status"] == "draft"
                    assert (
                        await call(
                            "run_read", action="operations_lookup", arguments={"request_id": intent}
                        )
                        == draft
                    )
                events = await client.get(
                    "/api/v1/audit/events", headers=staff, params={"source": "mcp"}
                )
                assert events.status_code == 200
                confirmed = [
                    row
                    for row in events.json()["items"]
                    if row["operation_id"] == pending["operation_id"]
                ]
                assert {row["origin"] for row in confirmed} == {"firstout", "mcp"}
                assert {row["actor"] for row in confirmed} == {user.email}
                assert all(row["token_id"] == issued.json()["token"]["id"] for row in confirmed)
