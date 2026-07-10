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
from app.models.photo_ingredient import PhotoIngredient
from app.tenant import owned_by_user


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

    async def get_by_photo_id(self, photo_id: int) -> Optional[PhotoAnalysis]:
        stmt = select(PhotoAnalysis).where(
            owned_by_user(PhotoAnalysis.user_id), PhotoAnalysis.photo_id == photo_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_photo_id_with_ingredients(self, photo_id: int) -> Optional[PhotoAnalysis]:
        stmt = (
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(owned_by_user(PhotoAnalysis.user_id), PhotoAnalysis.photo_id == photo_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_photo_id_with_ingredients_and_photo(
        self, photo_id: int
    ) -> Optional[PhotoAnalysis]:
        stmt = (
            select(PhotoAnalysis)
            .options(selectinload(PhotoAnalysis.ingredients), selectinload(PhotoAnalysis.photo))
            .where(owned_by_user(PhotoAnalysis.user_id), PhotoAnalysis.photo_id == photo_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_confirmed_with_entry_dates(
        self,
    ) -> list[tuple[PhotoAnalysis, datetime.date]]:
        """Confirmed, named analyses joined to their entry date, most-recent first.

        Backs ``MealService.list_recent`` -- a cross-domain (PhotoAnalysis/Photo/
        Entry) read that doesn't belong to any single domain's CRUD, so it lives
        here since PhotoAnalysis is the selected row.
        """
        stmt = (
            select(PhotoAnalysis, Entry.date)
            .join(Photo, PhotoAnalysis.photo_id == Photo.id)
            .join(Entry, Photo.entry_id == Entry.id)
            # selectinload is mandatory: compute_signal_from_analyses walks
            # analysis.ingredients, and a lazy load here would raise MissingGreenlet.
            .options(selectinload(PhotoAnalysis.ingredients))
            .where(
                owned_by_user(Entry.user_id),
                PhotoAnalysis.status == "confirmed",
                PhotoAnalysis.dish_name.isnot(None),
            )
            .order_by(Entry.date.desc(), PhotoAnalysis.photo_id.desc())
        )
        return list((await self.db.execute(stmt)).all())


class PhotoIngredientCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, ingredient_id: int) -> Optional[PhotoIngredient]:
        stmt = select(PhotoIngredient).where(
            owned_by_user(PhotoIngredient.user_id), PhotoIngredient.id == ingredient_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
