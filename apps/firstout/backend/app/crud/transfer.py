from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transfer import Transfer, TransferLine, TransferStatus
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx


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

    async def get_by_id(
        self, transfer_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[Transfer]:
        stmt = (
            select(Transfer)
            .options(*self._options())
            .where(Transfer.id == transfer_id, Transfer.team_id == tenant_id_ctx.get())
        )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(stmt)).scalar_one_or_none()

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

    async def list_by_pick_id(self, pick_id: uuid.UUID) -> list[Transfer]:
        result = await self.db.execute(
            select(Transfer).options(*self._options()).where(Transfer.pick_id == pick_id)
        )
        return list(result.scalars().all())

    async def get_next_transfer_number(self) -> str:
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("transfer")
