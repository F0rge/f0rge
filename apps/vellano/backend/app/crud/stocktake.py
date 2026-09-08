from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.sku import Sku
from app.models.stocktake import Stocktake, StocktakeLine, StocktakeStatus
from f0rge_db.crud import BaseCRUD


class StocktakeCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, stocktake_id: uuid.UUID) -> Optional[Stocktake]:
        return (
            await self.db.execute(
                select(Stocktake)
                .options(
                    selectinload(Stocktake.location),
                    selectinload(Stocktake.lines).selectinload(StocktakeLine.sku),
                )
                .where(Stocktake.id == stocktake_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Stocktake]:
        result = await self.db.execute(
            select(Stocktake)
            .options(
                selectinload(Stocktake.location),
                selectinload(Stocktake.lines).selectinload(StocktakeLine.sku),
            )
            .order_by(Stocktake.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_in_progress_for_location(self, location_id: uuid.UUID) -> Optional[Stocktake]:
        return (
            await self.db.execute(
                select(Stocktake).where(
                    Stocktake.location_id == location_id,
                    Stocktake.status == StocktakeStatus.IN_PROGRESS,
                )
            )
        ).scalar_one_or_none()


class StocktakeLineCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(
        self,
        stocktake_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> Optional[StocktakeLine]:
        return (
            await self.db.execute(
                select(StocktakeLine)
                .options(selectinload(StocktakeLine.sku))
                .where(
                    StocktakeLine.id == line_id,
                    StocktakeLine.stocktake_id == stocktake_id,
                )
            )
        ).scalar_one_or_none()

    async def get_by_barcode(
        self,
        stocktake_id: uuid.UUID,
        barcode: str,
    ) -> Optional[StocktakeLine]:
        return (
            await self.db.execute(
                select(StocktakeLine)
                .join(Sku, StocktakeLine.sku_id == Sku.id)
                .options(selectinload(StocktakeLine.sku))
                .where(
                    StocktakeLine.stocktake_id == stocktake_id,
                    Sku.our_barcode == barcode,
                )
            )
        ).scalar_one_or_none()
