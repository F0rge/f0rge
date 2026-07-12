from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
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
