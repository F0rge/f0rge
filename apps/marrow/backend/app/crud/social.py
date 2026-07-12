from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.auth import UserCRUD
from app.models.user import User
from app.schemas.social import normalize_handle


class SocialCRUD(UserCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_handle(self, handle: str) -> Optional[User]:
        normalized = normalize_handle(handle)
        return (
            await self.db.execute(select(User).where(User.handle == normalized))
        ).scalar_one_or_none()

    async def is_handle_taken(self, handle: str) -> bool:
        user = await self.get_by_handle(handle)
        return user is not None
