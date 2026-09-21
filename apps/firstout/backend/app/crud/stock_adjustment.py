from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.stock_adjustment import StockAdjustment, StockAdjustmentLine
from f0rge_db.crud import BaseCRUD


class StockAdjustmentCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, adjustment_id: uuid.UUID) -> Optional[StockAdjustment]:
        return (
            await self.db.execute(
                select(StockAdjustment)
                .options(
                    selectinload(StockAdjustment.location),
                    selectinload(StockAdjustment.lines).selectinload(StockAdjustmentLine.sku),
                )
                .where(StockAdjustment.id == adjustment_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[StockAdjustment]:
        result = await self.db.execute(
            select(StockAdjustment)
            .options(
                selectinload(StockAdjustment.location),
                selectinload(StockAdjustment.lines).selectinload(StockAdjustmentLine.sku),
            )
            .order_by(StockAdjustment.created_at.desc())
        )
        return list(result.scalars().all())


class StockAdjustmentLineCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(
        self,
        adjustment_id: uuid.UUID,
        line_id: uuid.UUID,
    ) -> Optional[StockAdjustmentLine]:
        return (
            await self.db.execute(
                select(StockAdjustmentLine)
                .options(selectinload(StockAdjustmentLine.sku))
                .where(
                    StockAdjustmentLine.id == line_id,
                    StockAdjustmentLine.adjustment_id == adjustment_id,
                )
            )
        ).scalar_one_or_none()
