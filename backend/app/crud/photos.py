from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.photo import Photo
from app.tenant import owned_by_user


class PhotoCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, photo_id: int) -> Optional[Photo]:
        return await self.get_by_id_owned(photo_id)

    async def get_by_id_owned(self, photo_id: int) -> Optional[Photo]:
        stmt = select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_user_id(self, photo_id: int) -> Optional[uuid.UUID]:
        stmt = select(Photo.user_id).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_filenames_for_entry(self, entry_id: int) -> list[str]:
        stmt = select(Photo.filename).where(
            owned_by_user(Photo.user_id), Photo.entry_id == entry_id
        )
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def list_filenames_for_user(self) -> list[str]:
        stmt = select(Photo.filename).where(owned_by_user(Photo.user_id))
        return [row[0] for row in (await self.db.execute(stmt)).all()]
