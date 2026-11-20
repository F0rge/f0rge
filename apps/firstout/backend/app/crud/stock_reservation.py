from __future__ import annotations

import datetime
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, delete, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import LocationStock
from app.models.location import Location, LocationType
from app.models.stock_reservation import StockReservation as Reservation
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx

Holder = tuple[str, uuid.UUID]
# Locations whose stock the company can sell from; on-water and other types do not count.
_SELLABLE_TYPES = (LocationType.SHOWROOM, LocationType.WAREHOUSE)


def sku_lock_key(team_id: uuid.UUID, sku_id: uuid.UUID) -> int:
    """Stable signed 64-bit advisory-lock key for one (tenant, SKU) pair."""
    digest = hashlib.blake2b(f"stock-reservation:{team_id}:{sku_id}".encode(), digest_size=8)
    return int.from_bytes(digest.digest(), "big", signed=True)


def _live(now: datetime.datetime):
    return or_(Reservation.expires_at.is_(None), Reservation.expires_at > now)


def _not_holder(holder: Optional[Holder]):
    if holder is None:
        return True
    return not_(and_(Reservation.holder_kind == holder[0], Reservation.holder_id == holder[1]))


class StockReservationCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def lock_sku(self, sku_id: uuid.UUID) -> None:
        """Serialise reservers of one SKU until the transaction ends."""
        await self.db.execute(
            select(func.pg_advisory_xact_lock(sku_lock_key(tenant_id_ctx.get(), sku_id)))
        )

    async def company_on_hand(self, sku_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
        rows = await self.db.execute(
            select(LocationStock.sku_id, func.sum(LocationStock.on_hand))
            .join(Location, Location.id == LocationStock.location_id)
            .where(
                LocationStock.team_id == tenant_id_ctx.get(),
                LocationStock.sku_id.in_(sku_ids),
                Location.is_archived.is_(False),
                Location.type.in_(_SELLABLE_TYPES),
            )
            .group_by(LocationStock.sku_id)
        )
        return {sku_id: total for sku_id, total in rows}

    async def reserved_by_others(
        self,
        now: datetime.datetime,
        exclude: Optional[Holder],
        sku_ids: Optional[list[uuid.UUID]] = None,
    ) -> dict[uuid.UUID, int]:
        query = (
            select(Reservation.sku_id, func.sum(Reservation.qty))
            .where(Reservation.team_id == tenant_id_ctx.get(), _live(now), _not_holder(exclude))
            .group_by(Reservation.sku_id)
        )
        if sku_ids is not None:
            query = query.where(Reservation.sku_id.in_(sku_ids))
        return {sku_id: int(total) for sku_id, total in await self.db.execute(query)}

    async def blocking(
        self,
        now: datetime.datetime,
        exclude: Optional[Holder],
        sku_ids: Optional[list[uuid.UUID]] = None,
    ) -> dict[uuid.UUID, dict]:
        """Per SKU, the live other-holder reservation that frees soonest (never-expiring last)."""
        query = (
            select(
                Reservation.sku_id,
                Reservation.location_id,
                Location.name,
                Reservation.holder_kind,
                Reservation.expires_at,
            )
            .join(Location, Location.id == Reservation.location_id)
            .where(Reservation.team_id == tenant_id_ctx.get(), _live(now), _not_holder(exclude))
            .distinct(Reservation.sku_id)
            .order_by(Reservation.sku_id, Reservation.expires_at.asc().nulls_last())
        )
        if sku_ids is not None:
            query = query.where(Reservation.sku_id.in_(sku_ids))
        return {
            sku_id: {
                "location_id": location_id,
                "location_name": name,
                "holder_kind": kind,
                "expires_at": expires_at,
            }
            for sku_id, location_id, name, kind, expires_at in await self.db.execute(query)
        }

    async def held_by(self, holder: Holder) -> dict[uuid.UUID, Reservation]:
        query = (
            select(Reservation)
            .where(
                Reservation.team_id == tenant_id_ctx.get(),
                Reservation.holder_kind == holder[0],
                Reservation.holder_id == holder[1],
            )
            .execution_options(populate_existing=True)
        )
        return {row.sku_id: row for row in await self.db.scalars(query)}

    async def delete_expired(self, now: datetime.datetime) -> None:
        await self.db.execute(
            delete(Reservation)
            .where(
                Reservation.team_id == tenant_id_ctx.get(),
                Reservation.expires_at <= now,
            )
            .execution_options(synchronize_session=False)
        )
