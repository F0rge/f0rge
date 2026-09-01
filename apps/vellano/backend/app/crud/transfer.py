from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transfer import Transfer, TransferLine, TransferStatus
from f0rge_db.crud import BaseCRUD


class TransferCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _options(self) -> tuple:
        return (
            selectinload(Transfer.from_location),
            selectinload(Transfer.to_location),
            selectinload(Transfer.created_by),
            selectinload(Transfer.dispatched_by),
            selectinload(Transfer.received_by),
            selectinload(Transfer.lines).selectinload(TransferLine.sku),
        )

    async def get_by_id(self, transfer_id: uuid.UUID) -> Optional[Transfer]:
        return (
            await self.db.execute(
                select(Transfer).options(*self._options()).where(Transfer.id == transfer_id)
            )
        ).scalar_one_or_none()

    async def list_all(
        self,
        status: Optional[TransferStatus] = None,
        to_location_id: Optional[uuid.UUID] = None,
    ) -> list[Transfer]:
        stmt = select(Transfer).options(*self._options())
        if status is not None:
            stmt = stmt.where(Transfer.status == status)
        if to_location_id is not None:
            stmt = stmt.where(Transfer.to_location_id == to_location_id)
        stmt = stmt.order_by(Transfer.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_next_transfer_number(self) -> str:
        result = await self.db.execute(
            select(Transfer.transfer_number).order_by(Transfer.transfer_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "TRF-0001"
        num = int(last.split("-")[1]) + 1
        return f"TRF-{num:04d}"
