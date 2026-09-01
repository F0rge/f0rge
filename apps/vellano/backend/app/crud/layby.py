from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.layby import Layby, LaybyLine
from f0rge_db.crud import BaseCRUD


class LaybyCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, layby_id: uuid.UUID) -> Optional[Layby]:
        return (
            await self.db.execute(
                select(Layby)
                .options(
                    selectinload(Layby.customer),
                    selectinload(Layby.location),
                    selectinload(Layby.lines).selectinload(LaybyLine.sku),
                    selectinload(Layby.payments),
                )
                .where(Layby.id == layby_id)
            )
        ).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[Layby]:
        result = await self.db.execute(
            select(Layby)
            .options(
                selectinload(Layby.customer),
                selectinload(Layby.location),
                selectinload(Layby.lines).selectinload(LaybyLine.sku),
                selectinload(Layby.payments),
            )
            .where(Layby.customer_id == customer_id)
            .order_by(Layby.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Layby]:
        result = await self.db.execute(
            select(Layby)
            .options(
                selectinload(Layby.customer),
                selectinload(Layby.location),
                selectinload(Layby.lines).selectinload(LaybyLine.sku),
                selectinload(Layby.payments),
            )
            .order_by(Layby.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_next_layby_number(self) -> str:
        result = await self.db.execute(
            select(Layby.layby_number).order_by(Layby.layby_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "LB-0001"
        num = int(last.split("-")[1]) + 1
        return f"LB-{num:04d}"
