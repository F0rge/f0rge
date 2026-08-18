from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from f0rge_db.tenant import owned_by_user


class PhotoIngredientCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, ingredient_id: int) -> Optional[PhotoIngredient]:
        stmt = select(PhotoIngredient).where(
            owned_by_user(PhotoIngredient.user_id), PhotoIngredient.id == ingredient_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_editing(self, ingredient_id: int) -> Optional[PhotoIngredient]:
        """Owner access, or participant on a shared meal placement."""
        owned = await self.get_by_id(ingredient_id)
        if owned is not None:
            return owned
        stmt = (
            select(PhotoIngredient)
            .join(PhotoAnalysis, PhotoAnalysis.id == PhotoIngredient.analysis_id)
            .join(Photo, Photo.meal_id == PhotoAnalysis.meal_id)
            .where(
                PhotoIngredient.id == ingredient_id,
                owned_by_user(Photo.user_id),
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def delete_for_analysis(self, analysis_id: int) -> None:
        """Remove all ingredients for an analysis (retry-safe complete)."""
        await self.db.execute(
            delete(PhotoIngredient).where(
                owned_by_user(PhotoIngredient.user_id),
                PhotoIngredient.analysis_id == analysis_id,
            )
        )
        await self.flush()
