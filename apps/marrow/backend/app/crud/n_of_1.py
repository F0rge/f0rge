from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.n_of_1_slot import NOf1Slot
from f0rge_db.tenant import owned_by_user


class NOf1CRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_for_user(self) -> Optional[NOf1Slot]:
        stmt = select(NOf1Slot).where(owned_by_user(NOf1Slot.user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()
