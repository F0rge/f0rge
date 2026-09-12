from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.n_of_1 import NOf1CRUD
from app.models.n_of_1_slot import NOf1Slot
from app.schemas.hypothesis import NOf1Upsert
from f0rge_db.tenant import current_user_id


class NOf1Service:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = NOf1CRUD(db)

    async def get(self) -> Optional[NOf1Slot]:
        return await self.crud.get_for_user()

    async def upsert(self, data: NOf1Upsert) -> NOf1Slot:
        row = await self.crud.get_for_user()
        if row is None:
            row = NOf1Slot(
                user_id=current_user_id(),
                change=data.change,
                start=data.start,
                watch_field=data.watch_field,
                stop_rule=data.stop_rule,
            )
            self.crud.add(row)
        else:
            row.change = data.change
            row.start = data.start
            row.watch_field = data.watch_field
            row.stop_rule = data.stop_rule
        return await self.crud.commit_refresh(row)
