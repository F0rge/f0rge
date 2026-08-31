from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team
from app.models.user import User
from f0rge_db.crud import BaseCRUD


class TeamCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, team_id: uuid.UUID) -> Optional[Team]:
        return (await self.db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()

    async def get_first(self) -> Optional[Team]:
        return (await self.db.execute(select(Team).limit(1))).scalar_one_or_none()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Team))
        return int(result.scalar_one())


class UserCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return (
            await self.db.execute(
                select(User).options(selectinload(User.team)).where(User.id == user_id)
            )
        ).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        return (
            await self.db.execute(
                select(User).options(selectinload(User.team)).where(User.email == email)
            )
        ).scalar_one_or_none()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def list_all(self) -> list[User]:
        result = await self.db.execute(
            select(User).options(selectinload(User.team)).order_by(User.email)
        )
        return list(result.scalars().all())
