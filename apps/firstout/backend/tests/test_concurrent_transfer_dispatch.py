"""Two transfers must not take the same on-hand unit."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.crud.purchase_order import LocationStockCRUD
from app.models.document_sequence import DocumentSequence
from app.models.inventory import LocationStock
from app.models.location import Location
from app.models.location_bin import BinStock
from app.models.sku import Sku
from app.models.transfer import Transfer, TransferStatus
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User
from app.schemas.transfer import (
    TransferCreate,
    TransferLineCreate,
    TransferReceive,
    TransferReceiveLine,
)
from app.services.stock_movements import StockMovementService
from app.services.transfers import TransferService
from f0rge_core.exceptions import ConflictError


async def _snapshot_sequences(session: AsyncSession) -> dict[str, int]:
    rows = (await session.execute(select(DocumentSequence))).scalars().all()
    return {row.doc_type: int(row.next_value) for row in rows}


async def _restore_sequences(session: AsyncSession, before: dict[str, int]) -> None:
    rows = (await session.execute(select(DocumentSequence))).scalars().all()
    for row in rows:
        if row.doc_type in before:
            row.next_value = before[row.doc_type]
        else:
            await session.delete(row)


async def test_concurrent_transfer_dispatch_cannot_take_the_same_unit(async_engine) -> None:
    maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)
    sku_id = None
    source_location_id = None
    source_stock_id = None
    transfer_ids: list[uuid.UUID] = []
    sequences: dict[str, int] = {}
    user_id = None

    async with maker() as session:
        sequences = await _snapshot_sequences(session)
        user = (
            await session.execute(select(User).where(User.email == "owner@example.com"))
        ).scalar_one()
        user_id = user.id
        locations = {
            row.name: row for row in (await session.execute(select(Location))).scalars().all()
        }
        source_location_id = locations["Kramerville"].id
        sku = Sku(
            our_ref="CONC-SOFA",
            our_barcode="CONC-SOFA",
            name="Concurrent sofa",
            design="concurrent-sofa",
            fabric="linen",
            retail_ex_vat=Decimal("1000.00"),
        )
        session.add(sku)
        await session.flush()
        sku_id = sku.id
        await StockMovementService(session).apply_incoming_qty(
            sku_id=sku.id,
            location_id=source_location_id,
            qty=1,
            unit_cost_zar=Decimal("100.00"),
            user_id=user.id,
            source=UnitCostAuditSource.OPENING,
            note="one sofa",
            record_audit=False,
        )
        source = (
            await session.execute(
                select(LocationStock).where(
                    LocationStock.sku_id == sku.id,
                    LocationStock.location_id == source_location_id,
                )
            )
        ).scalar_one()
        source_stock_id = source.id
        assert source.on_hand == 1
        service = TransferService(session)
        for _ in range(2):
            created = await service.create(
                TransferCreate(
                    from_location_id=source_location_id,
                    to_location_id=locations["Bedfordview"].id,
                    lines=[TransferLineCreate(sku_id=sku.id, qty=1)],
                ),
                user.id,
            )
            transfer_ids.append(created.id)

    assert sku_id is not None
    assert source_location_id is not None
    assert source_stock_id is not None
    assert user_id is not None

    reads = {"n": 0}
    both_observed = asyncio.Event()
    original_get = LocationStockCRUD.get_by_sku_and_location

    async def _counting_get(self, sku, location_id, *args, **kwargs):
        row = await original_get(self, sku, location_id, *args, **kwargs)
        if sku == sku_id and location_id == source_location_id:
            reads["n"] += 1
            if reads["n"] >= 4:
                both_observed.set()
        return row

    LocationStockCRUD.get_by_sku_and_location = _counting_get  # type: ignore[method-assign]

    probe = maker()
    await probe.__aenter__()
    await probe.begin()
    await probe.execute(
        select(LocationStock).where(LocationStock.id == source_stock_id).with_for_update()
    )

    async def _dispatch(transfer_id: uuid.UUID):
        async with maker() as session:
            return await TransferService(session).dispatch(transfer_id, user_id)

    try:
        tasks = [asyncio.create_task(_dispatch(transfer_id)) for transfer_id in transfer_ids]
        try:
            await asyncio.wait_for(both_observed.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
        await probe.commit()
        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        LocationStockCRUD.get_by_sku_and_location = original_get  # type: ignore[method-assign]
        await probe.close()

    try:
        successes = [result for result in results if not isinstance(result, Exception)]
        conflicts = [result for result in results if isinstance(result, ConflictError)]
        unexpected = [
            result
            for result in results
            if isinstance(result, Exception) and not isinstance(result, ConflictError)
        ]
        assert unexpected == [], unexpected
        assert len(successes) == 1, (len(successes), len(conflicts), reads["n"])
        assert len(conflicts) == 1

        async with maker() as session:
            for transfer_id in transfer_ids:
                transfer = (
                    await session.execute(
                        select(Transfer)
                        .options(selectinload(Transfer.lines))
                        .where(Transfer.id == transfer_id)
                    )
                ).scalar_one()
                if transfer.status != TransferStatus.IN_TRANSIT:
                    continue
                await TransferService(session).receive(
                    transfer_id,
                    TransferReceive(
                        lines=[
                            TransferReceiveLine(line_id=line.id, qty_received=line.qty_dispatched)
                            for line in transfer.lines
                        ]
                    ),
                    user_id,
                )
            company_on_hand = await session.scalar(
                select(func.coalesce(func.sum(LocationStock.on_hand), 0)).where(
                    LocationStock.sku_id == sku_id
                )
            )
            assert int(company_on_hand or 0) == 1
    finally:
        async with maker() as session:
            async with session.begin():
                if transfer_ids:
                    await session.execute(delete(Transfer).where(Transfer.id.in_(transfer_ids)))
                if sku_id is not None:
                    await session.execute(delete(BinStock).where(BinStock.sku_id == sku_id))
                    await session.execute(
                        delete(LocationStock).where(LocationStock.sku_id == sku_id)
                    )
                    await session.execute(delete(Sku).where(Sku.id == sku_id))
                await _restore_sequences(session, sequences)
