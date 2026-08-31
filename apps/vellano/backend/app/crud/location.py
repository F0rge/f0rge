from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location
from f0rge_db.crud import BaseCRUD


class LocationCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, location_id: uuid.UUID) -> Optional[Location]:
        return (
            await self.db.execute(select(Location).where(Location.id == location_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Location]:
        result = await self.db.execute(select(Location).order_by(Location.name))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Location))
        return int(result.scalar_one())

    async def get_active_by_name_insensitive(
        self,
        name: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> Optional[Location]:
        stmt = select(Location).where(
            func.lower(Location.name) == name.lower(),
            Location.is_archived.is_(False),
        )
        if exclude_id is not None:
            stmt = stmt.where(Location.id != exclude_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
