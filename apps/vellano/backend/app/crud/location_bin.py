from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.location_bin import BinStock, LocationBin
from f0rge_db.crud import BaseCRUD


class LocationBinCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, bin_id: uuid.UUID) -> Optional[LocationBin]:
        return (
            await self.db.execute(select(LocationBin).where(LocationBin.id == bin_id))
        ).scalar_one_or_none()

    async def list_by_location(self, location_id: uuid.UUID) -> list[LocationBin]:
        result = await self.db.execute(
            select(LocationBin)
            .where(LocationBin.location_id == location_id)
            .order_by(LocationBin.is_default.desc(), LocationBin.code)
        )
        return list(result.scalars().all())

    async def get_active_default(self, location_id: uuid.UUID) -> Optional[LocationBin]:
        return (
            await self.db.execute(
                select(LocationBin).where(
                    LocationBin.location_id == location_id,
                    LocationBin.is_default.is_(True),
                    LocationBin.is_archived.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def get_by_slot(
        self,
        location_id: uuid.UUID,
        row_code: str,
        bay: int,
        level: int,
    ) -> Optional[LocationBin]:
        return (
            await self.db.execute(
                select(LocationBin).where(
                    LocationBin.location_id == location_id,
                    LocationBin.row_code == row_code,
                    LocationBin.bay == bay,
                    LocationBin.level == level,
                )
            )
        ).scalar_one_or_none()

    async def get_active_by_code(
        self,
        location_id: uuid.UUID,
        code: str,
    ) -> Optional[LocationBin]:
        return (
            await self.db.execute(
                select(LocationBin).where(
                    LocationBin.location_id == location_id,
                    func.lower(LocationBin.code) == code.lower(),
                    LocationBin.is_archived.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def list_active(self, location_id: uuid.UUID) -> list[LocationBin]:
        result = await self.db.execute(
            select(LocationBin).where(
                LocationBin.location_id == location_id,
                LocationBin.is_archived.is_(False),
            )
        )
        return list(result.scalars().all())

    async def clear_default(self, location_id: uuid.UUID, exclude_id: uuid.UUID) -> None:
        current = await self.get_active_default(location_id)
        if current is not None and current.id != exclude_id:
            current.is_default = False


class BinStockCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_sku_and_bin(
        self,
        sku_id: uuid.UUID,
        bin_id: uuid.UUID,
    ) -> Optional[BinStock]:
        return (
            await self.db.execute(
                select(BinStock).where(
                    BinStock.sku_id == sku_id,
                    BinStock.bin_id == bin_id,
                )
            )
        ).scalar_one_or_none()

    async def sum_on_hand_for_sku_location(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.sum(BinStock.on_hand), 0))
            .select_from(BinStock)
            .join(LocationBin, LocationBin.id == BinStock.bin_id)
            .where(
                BinStock.sku_id == sku_id,
                LocationBin.location_id == location_id,
            )
        )
        return int(result.scalar_one())

    async def list_nonzero_for_skus(self, sku_ids: list[uuid.UUID]) -> list[BinStock]:
        if not sku_ids:
            return []
        result = await self.db.execute(
            select(BinStock)
            .options(selectinload(BinStock.bin))
            .where(BinStock.sku_id.in_(sku_ids), BinStock.on_hand > 0)
        )
        return list(result.scalars().all())
