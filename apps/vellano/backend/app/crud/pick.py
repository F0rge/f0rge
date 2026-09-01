from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.pick import Pick, PickAllocation, PickLine
from f0rge_db.crud import BaseCRUD


class PickCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _options(self) -> tuple:
        return (
            selectinload(Pick.kit_sku),
            selectinload(Pick.customer),
            selectinload(Pick.staging_location),
            selectinload(Pick.invoice),
            selectinload(Pick.lines).selectinload(PickLine.sku),
            selectinload(Pick.lines)
            .selectinload(PickLine.allocations)
            .selectinload(PickAllocation.location),
        )

    async def get_by_id(self, pick_id: uuid.UUID) -> Optional[Pick]:
        return (
            await self.db.execute(select(Pick).options(*self._options()).where(Pick.id == pick_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Pick]:
        result = await self.db.execute(
            select(Pick).options(*self._options()).order_by(Pick.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_next_pick_number(self) -> str:
        result = await self.db.execute(select(Pick.number).order_by(Pick.number.desc()).limit(1))
        last = result.scalar_one_or_none()
        if last is None:
            return "PCK-0001"
        num = int(last.split("-")[1]) + 1
        return f"PCK-{num:04d}"
