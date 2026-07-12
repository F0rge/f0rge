from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import BaseCRUD
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from f0rge_db.tenant import owned_by_user


class PhotoAnalysisCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, analysis_id: int) -> Optional[PhotoAnalysis]:
        stmt = select(PhotoAnalysis).where(
            owned_by_user(PhotoAnalysis.user_id), PhotoAnalysis.id == analysis_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id_with_ingredients(self, analysis_id: int) -> Optional[PhotoAnalysis]:
        stmt = (
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(owned_by_user(PhotoAnalysis.user_id), PhotoAnalysis.id == analysis_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_meal_id(self, meal_id: int) -> Optional[PhotoAnalysis]:
        stmt = select(PhotoAnalysis).where(PhotoAnalysis.meal_id == meal_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_meal_id_with_ingredients(self, meal_id: int) -> Optional[PhotoAnalysis]:
        stmt = (
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(PhotoAnalysis.meal_id == meal_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_photo_id(self, photo_id: int) -> Optional[PhotoAnalysis]:
        return await self.get_for_photo(photo_id)

    async def get_by_photo_id_with_ingredients(self, photo_id: int) -> Optional[PhotoAnalysis]:
        return await self.get_for_photo_with_ingredients(photo_id)

    async def get_for_photo(self, photo_id: int) -> Optional[PhotoAnalysis]:
        """Resolve the canonical meal analysis for a photo placement."""
        photo = (
            await self.db.execute(
                select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
            )
        ).scalar_one_or_none()
        if photo is None:
            return None
        return await self.get_by_meal_id(photo.meal_id)

    async def get_for_photo_with_ingredients(self, photo_id: int) -> Optional[PhotoAnalysis]:
        photo = (
            await self.db.execute(
                select(Photo).where(owned_by_user(Photo.user_id), Photo.id == photo_id)
            )
        ).scalar_one_or_none()
        if photo is None:
            return None
        return await self.get_by_meal_id_with_ingredients(photo.meal_id)

    async def get_by_photo_id_with_ingredients_and_photo(
        self, photo_id: int
    ) -> Optional[PhotoAnalysis]:
        stmt = (
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients), selectinload(PhotoAnalysis.photo))
            .join(Photo, Photo.meal_id == PhotoAnalysis.meal_id)
            .where(owned_by_user(Photo.user_id), Photo.id == photo_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_confirmed_with_entry_dates(
        self,
    ) -> list[tuple[PhotoAnalysis, datetime.date]]:
        """Confirmed, named analyses joined to their entry date, most-recent first."""
        stmt = (
            select(PhotoAnalysis, Entry.date)
            .join(Photo, PhotoAnalysis.meal_id == Photo.meal_id)
            .join(Entry, Photo.entry_id == Entry.id)
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(
                owned_by_user(Entry.user_id),
                PhotoAnalysis.status == "confirmed",
                PhotoAnalysis.dish_name.isnot(None),
            )
            .order_by(Entry.date.desc(), Photo.id.desc())
        )
        return list((await self.db.execute(stmt)).all())
