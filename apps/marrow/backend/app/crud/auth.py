from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.user import User


class UserCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return (await self.db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        return (await self.db.execute(select(User).where(User.email == email))).scalar_one_or_none()

    async def get_by_handle(self, handle: str) -> Optional[User]:
        return (
            await self.db.execute(select(User).where(User.handle == handle))
        ).scalar_one_or_none()
