from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Location, LocationType
from f0rge_db.crud import BaseCRUD
from f0rge_db.organisation import tenant_id_ctx


class LocationCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, location_id: uuid.UUID) -> Optional[Location]:
        return (
            await self.db.execute(
                select(Location)
                .where(Location.id == location_id, Location.team_id == tenant_id_ctx.get())
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def lock_for_stocktake(self, location_id: uuid.UUID, *, starting: bool) -> bool:
        # Multiple stock movements can proceed together. Beginning a count must
        # wait until their balances are final before taking the opening snapshot.
        stmt = select(Location.id).where(
            Location.id == location_id, Location.team_id == tenant_id_ctx.get()
        )
        locked_id = await self.db.scalar(
            stmt.with_for_update(key_share=True) if starting else stmt.with_for_update(read=True)
        )
        return locked_id is not None

    async def list_all(self) -> list[Location]:
        result = await self.db.execute(select(Location).order_by(Location.name))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Location))
        return int(result.scalar_one())

    async def get_active_by_name_and_type(
        self,
        name: str,
        location_type: LocationType,
    ) -> Optional[Location]:
        stmt = select(Location).where(
            func.lower(Location.name) == name.lower(),
            Location.type == location_type,
            Location.is_archived.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

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
