"""Company-wide stock availability and reservations.

company_available = on-hand at active showroom and warehouse locations
                    - live reservations held by anyone but the caller's holder.
The server is the only authority on this number; callers only display it.
"""

from __future__ import annotations

import datetime
import math
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.stock_reservation import Holder, StockReservationCRUD
from app.models.stock_reservation import StockReservation
from app.models.team_settings import DEFAULT_TILL_HOLD_HOURS, TeamSettings
from f0rge_db.organisation import tenant_id_ctx


class StockUnavailable(Exception):
    """Raising a reservation above what the company has unreserved."""

    def __init__(self, sku_id: uuid.UUID, available: int, blocking: Optional[dict]) -> None:
        super().__init__(f"Only {available} available")
        self.sku_id = sku_id
        self.available = available
        self.blocking = blocking


class StockAvailability:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = StockReservationCRUD(db)

    async def company_available(
        self, sku_ids: list[uuid.UUID], now: datetime.datetime, exclude: Optional[Holder] = None
    ) -> dict[uuid.UUID, Decimal]:
        """May be negative; clients are shown max(0, value)."""
        on_hand = await self.crud.company_on_hand(sku_ids)
        others = await self.crud.reserved_by_others(now, exclude, sku_ids)
        return {s: on_hand.get(s, Decimal(0)) - others.get(s, 0) for s in sku_ids}

    async def reserve(
        self,
        holder: Holder,
        location_id: uuid.UUID,
        wanted: dict[uuid.UUID, int],
        expires_at: Optional[datetime.datetime],
        now: datetime.datetime,
    ) -> None:
        """Make the holder's reservations exactly ``wanted`` (SKU to qty).

        Raises are checked, under per-SKU advisory locks taken in sorted order, before
        anything is written; lowering or removing never fails.
        """
        existing = await self.crud.held_by(holder)
        raised = sorted(
            sku
            for sku, qty in wanted.items()
            if qty > (existing[sku].qty if sku in existing else 0)
        )
        for sku_id in raised:
            await self.crud.lock_sku(sku_id)
        if raised:
            available = await self.company_available(raised, now, holder)
            for sku_id in raised:
                if available[sku_id] < wanted[sku_id]:
                    blocking = (await self.crud.blocking(now, holder, [sku_id])).get(sku_id)
                    raise StockUnavailable(sku_id, max(0, math.floor(available[sku_id])), blocking)
        for sku_id, row in existing.items():
            if sku_id not in wanted:
                await self.db.delete(row)
        for sku_id, qty in wanted.items():
            row = existing.get(sku_id)
            if row is None:
                self.db.add(
                    StockReservation(
                        sku_id=sku_id,
                        qty=qty,
                        holder_kind=holder[0],
                        holder_id=holder[1],
                        location_id=location_id,
                        expires_at=expires_at,
                    )
                )
            else:
                row.qty = qty
                row.expires_at = expires_at

    async def others_at_till(
        self, now: datetime.datetime, own_basket_id: Optional[uuid.UUID]
    ) -> list[dict]:
        exclude = ("basket", own_basket_id) if own_basket_id else None
        reserved = await self.crud.reserved_by_others(now, exclude)
        blocking = await self.crud.blocking(now, exclude)
        return [
            {"sku_id": sku_id, "reserved_by_others": qty, "blocking": blocking.get(sku_id)}
            for sku_id, qty in reserved.items()
        ]

    async def hold_time(self) -> datetime.timedelta:
        hours = await self.db.scalar(
            select(TeamSettings.till_hold_hours).where(TeamSettings.team_id == tenant_id_ctx.get())
        )
        return datetime.timedelta(hours=hours or DEFAULT_TILL_HOLD_HOURS)

    async def move(
        self,
        source: Holder,
        target: Holder,
        expires_at: Optional[datetime.datetime],
    ) -> bool:
        """Hand all of one holder's reservations to another without ever freeing them.

        The target's own reservations are replaced. Returns False, changing nothing, when
        the source holds none.
        """
        if not await self.crud.held_by(source):
            return False
        await self.crud.release(target[0], [target[1]])
        await self.crud.move(source, target, expires_at)
        return True

    async def release(self, holder_kind: str, holder_ids: list[uuid.UUID]) -> None:
        if holder_ids:
            await self.crud.release(holder_kind, holder_ids)

    async def prune(self, now: datetime.datetime) -> None:
        await self.crud.delete_expired(now)
