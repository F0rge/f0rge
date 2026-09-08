from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.stock_return import StockReturn, StockReturnLine, StockReturnStatus
from f0rge_db.crud import BaseCRUD


class StockReturnCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, return_id: uuid.UUID) -> Optional[StockReturn]:
        return (
            await self.db.execute(
                select(StockReturn)
                .options(
                    selectinload(StockReturn.invoice),
                    selectinload(StockReturn.location),
                    selectinload(StockReturn.lines).selectinload(StockReturnLine.invoice_line),
                    selectinload(StockReturn.lines).selectinload(StockReturnLine.sku),
                )
                .where(StockReturn.id == return_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[StockReturn]:
        result = await self.db.execute(
            select(StockReturn)
            .options(
                selectinload(StockReturn.invoice),
                selectinload(StockReturn.location),
                selectinload(StockReturn.lines).selectinload(StockReturnLine.invoice_line),
                selectinload(StockReturn.lines).selectinload(StockReturnLine.sku),
            )
            .order_by(StockReturn.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_by_invoice_id(self, invoice_id: uuid.UUID) -> Optional[StockReturn]:
        return (
            await self.db.execute(
                select(StockReturn).where(
                    StockReturn.invoice_id == invoice_id,
                    StockReturn.status != StockReturnStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_next_return_number(self) -> str:
        result = await self.db.execute(
            select(StockReturn.return_number).order_by(StockReturn.return_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "RTN-0001"
        num = int(last.split("-")[1]) + 1
        return f"RTN-{num:04d}"
