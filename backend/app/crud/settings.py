from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.user_settings import UserSettings
from app.tenant import owned_by_user


class UserSettingsCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get(self) -> Optional[UserSettings]:
        stmt = select(UserSettings).where(owned_by_user(UserSettings.user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()
