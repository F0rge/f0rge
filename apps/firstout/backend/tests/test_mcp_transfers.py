"""Real committed stock transitions from independent staff and MCP sessions."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.crud.transfer import TransferCRUD
from app.models.inventory import LocationStock
from app.models.location import Location
from app.models.mcp_token import McpToken
from app.models.pick import Pick, PickSourceType, PickStatus
from app.models.transfer import Transfer, TransferStatus
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.stocktake import StocktakeCreate
from app.schemas.transfer import TransferCreate, TransferReceive
from app.services.locations import LocationSeedService
from app.services.mcp_transfers import (
    TRANSFER_ACTIONS,
    DispatchArguments,
    ReceiveArguments,
    TransferDraftArguments,
)
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.transfers import TransferService
from f0rge_core.exceptions import ConflictError, ValidationError
from f0rge_db.crud import unit_of_work
from tests.test_sku_archive_commit_races import isolated_requests


async def _stock_and_draft(db, actor, sku_id):
    source, dest = (await db.scalars(select(Location.id).order_by(Location.id))).all()
    await StockMovementService(db).apply_incoming_qty(
        sku_id,
        source,
        Decimal("1.25"),
        Decimal("40.00"),
        actor,
        UnitCostAuditSource.RECEIVE,
        "Opening balance",
        record_audit=False,
    )
    return TransferDraftArguments(
        from_location_id=source,
        to_location_id=dest,
        lines=[{"sku_id": sku_id, "qty": "1.25"}],
    )


@pytest.mark.parametrize("same_draft", [True, False], ids=["one-draft", "last-units"])
async def test_mcp_and_staff_competing_for_stock(second_postgres_url, same_draft):
    actions = {item.name: item for item in TRANSFER_ACTIONS}
    async with isolated_requests(second_postgres_url) as (maker, ids):
        actor = ids["actor"]
        token = McpToken(team_id=ids["team"], user_id=actor)
        async with maker() as db:
            await LocationSeedService(db).seed_if_empty()
            async with unit_of_work(db):
                draft = await _stock_and_draft(db, actor, ids["sku"])
                source, dest = draft.from_location_id, draft.to_location_id
                first = await actions["transfers_create_draft"].handler(db, token, draft)
                second = (
                    first
                    if same_draft
                    else await actions["transfers_create_draft"].handler(db, token, draft)
                )
                mcp_request = DispatchArguments(transfer_id=first["transfer_id"])
                staff_request = DispatchArguments(transfer_id=second["transfer_id"])

        async def dispatch(mcp):
            req = mcp_request if mcp else staff_request
            async with maker() as db:
                try:
                    if mcp:
                        async with unit_of_work(db):
                            await actions["transfers_dispatch"].handler(db, token, req)
                    else:
                        await TransferService(db).dispatch(req.transfer_id, actor)
                    return req.transfer_id
                except ConflictError:
                    return None

        results = await asyncio.wait_for(asyncio.gather(dispatch(True), dispatch(False)), 15)
        shipped = [result for result in results if result]
        assert len(shipped) == 1
        async with maker() as db:
            transfer = await TransferCRUD(db).get_by_id(shipped[0])
            assert transfer.dispatched_by_user_id == actor
            line_id = transfer.lines[0].id
            counts = ReceiveArguments(
                transfer_id=transfer.id, lines=[{"line_id": line_id, "qty_received": "1.25"}]
            )
            incorrect = ReceiveArguments(
                transfer_id=transfer.id, lines=[{"line_id": line_id, "qty_received": "1.20"}]
            )
            with pytest.raises(ValidationError):
                async with unit_of_work(db):
                    await actions["transfers_receive"].handler(db, token, incorrect)

        async def receive(mcp):
            async with maker() as db:
                try:
                    if mcp:
                        async with unit_of_work(db):
                            await actions["transfers_receive"].handler(db, token, counts)
                    else:
                        await TransferService(db).receive(
                            shipped[0], TransferReceive(lines=counts.lines), actor
                        )
                    return True
                except ConflictError:
                    return False

        assert sum(await asyncio.wait_for(asyncio.gather(receive(True), receive(False)), 15)) == 1
        async with maker() as db:
            balances = dict(
                (
                    await db.execute(
                        select(LocationStock.location_id, LocationStock.on_hand).where(
                            LocationStock.sku_id == ids["sku"]
                        )
                    )
                ).all()
            )
            assert balances == {source: Decimal("0"), dest: Decimal("1.25")}
            transfer = await TransferCRUD(db).get_by_id(shipped[0])
            assert transfer.received_by_user_id == actor
            assert transfer.lines[0].qty_received == Decimal("1.25")


async def test_stocktake_start_waits_for_committed_dispatch(second_postgres_url):
    actions = {item.name: item for item in TRANSFER_ACTIONS}
    async with isolated_requests(second_postgres_url) as (maker, ids):
        token = McpToken(team_id=ids["team"], user_id=ids["actor"])
        async with maker() as db:
            await LocationSeedService(db).seed_if_empty()
            async with unit_of_work(db):
                draft = await _stock_and_draft(db, ids["actor"], ids["sku"])
                receipt = await actions["transfers_create_draft"].handler(db, token, draft)
                assert receipt["href"] == "/transfers"

            req = DispatchArguments(transfer_id=receipt["transfer_id"])
            count = StocktakeCreate(location_id=draft.from_location_id)
            async with unit_of_work(db):
                await actions["transfers_dispatch"].handler(db, token, req)
                # Independent committed staff sessions must not take a stale opening
                # count while dispatch is waiting to persist its result and audit.
                async with maker() as counting:
                    await counting.execute(text("SET LOCAL lock_timeout = '200ms'"))
                    with pytest.raises(DBAPIError) as blocked:
                        await StocktakeService(counting).start(count, ids["actor"])
                    assert blocked.value.orig.sqlstate == "55P03"

            async with maker() as counting:
                sheet = await StocktakeService(counting).start(count, ids["actor"])
                assert (
                    next(line.expected_qty for line in sheet.lines if line.sku_id == ids["sku"])
                    == 0
                )


async def test_direct_dispatch_keeps_nonstandalone_or_large_transfers_in_warehouse(
    second_postgres_url,
):
    dispatch = next(action for action in TRANSFER_ACTIONS if action.name == "transfers_dispatch")
    async with isolated_requests(second_postgres_url) as (maker, ids):
        token = McpToken(team_id=ids["team"], user_id=ids["actor"])
        async with maker() as db:
            await LocationSeedService(db).seed_if_empty()
            async with unit_of_work(db):
                draft = await _stock_and_draft(db, ids["actor"], ids["sku"])
                pick = Pick(
                    number="PICK-TEST", source_type=PickSourceType.TILL, status=PickStatus.CONFIRMED
                )
                db.add(pick)
                await db.flush()
                service = TransferService(db)
                linked = await service.stage_draft(
                    TransferCreate(**draft.model_dump(), pick_id=pick.id), ids["actor"]
                )
                large = await service.stage_draft(
                    TransferCreate(
                        **draft.model_dump(exclude={"lines"}), lines=[draft.lines[0]] * 51
                    ),
                    ids["actor"],
                )

        for transfer, error, message in (
            (linked, ConflictError, "linked to a pick"),
            (large, ValidationError, "50 lines"),
        ):
            async with maker() as db:
                with pytest.raises(error, match=message):
                    async with unit_of_work(db):
                        await dispatch.handler(
                            db, token, DispatchArguments(transfer_id=transfer.id)
                        )
        async with maker() as db:
            statuses = await db.scalars(
                select(Transfer.status).where(Transfer.id.in_([linked.id, large.id]))
            )
            assert list(statuses) == [TransferStatus.DRAFT, TransferStatus.DRAFT]
            assert await db.scalar(
                select(LocationStock.on_hand).where(
                    LocationStock.sku_id == ids["sku"],
                    LocationStock.location_id == draft.from_location_id,
                )
            ) == Decimal("1.25")
