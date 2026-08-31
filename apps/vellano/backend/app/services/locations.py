from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.models.location import Location, LocationType
from app.schemas.location import LocationCreate, LocationUpdate
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class LocationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LocationCRUD(db)

    async def list(self) -> list[Location]:
        return await self.crud.list_all()

    async def create(self, data: LocationCreate) -> Location:
        await self._ensure_unique_active_name(data.name)
        location = Location(
            name=data.name,
            type=data.type,
        )
        await self.crud.add_and_flush(location)
        try:
            await self.crud.commit_refresh(location)
        except IntegrityError as exc:
            raise ConflictError("A location with this name already exists") from exc
        reloaded = await self.crud.get_by_id(location.id)
        assert reloaded is not None
        return reloaded

    async def update(self, location_id: uuid.UUID, data: LocationUpdate) -> Location:
        location = await self.crud.get_by_id(location_id)
        if location is None:
            raise NotFoundError("Location not found")

        if data.name is not None:
            await self._ensure_unique_active_name(data.name, exclude_id=location.id)
            location.name = data.name

        if data.is_archived is not None:
            if data.is_archived:
                location.is_archived = True
                location.archived_at = datetime.datetime.utcnow()
            else:
                await self._ensure_unique_active_name(location.name, exclude_id=location.id)
                location.is_archived = False
                location.archived_at = None

        try:
            await self.crud.commit_refresh(location)
        except IntegrityError as exc:
            raise ConflictError("A location with this name already exists") from exc
        reloaded = await self.crud.get_by_id(location.id)
        assert reloaded is not None
        return reloaded

    async def _ensure_unique_active_name(
        self,
        name: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        existing = await self.crud.get_active_by_name_insensitive(name, exclude_id)
        if existing is not None:
            raise ConflictError("A location with this name already exists")


class LocationSeedService:
    SEED_ROWS: tuple[tuple[str, LocationType], ...] = (
        ("Kramerville", LocationType.WAREHOUSE),
        ("Bedfordview", LocationType.SHOWROOM),
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LocationCRUD(db)

    async def seed_if_empty(self) -> None:
        if await self.crud.count() > 0:
            return

        async with unit_of_work(self.db):
            for name, location_type in self.SEED_ROWS:
                location = Location(name=name, type=location_type)
                await self.crud.add_and_flush(location)
