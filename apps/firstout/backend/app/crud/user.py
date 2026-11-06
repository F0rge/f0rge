from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from f0rge_db.organisation import tenant_id_ctx
from app.models.membership import Membership
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.team import Team
from app.models.user import User, UserRole
from f0rge_db.crud import BaseCRUD


class TeamCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, team_id: uuid.UUID) -> Optional[Team]:
        return (await self.db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()

    async def get_first(self) -> Optional[Team]:
        team_id = tenant_id_ctx.get()
        query = select(Team)
        if team_id is not None:
            query = query.where(Team.id == team_id)
        return (await self.db.execute(query.limit(1))).scalar_one_or_none()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Team))
        return int(result.scalar_one())


class UserCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        tenant_id = tenant_id_ctx.get()
        if tenant_id is not None:
            member = (
                await self.db.execute(
                    select(Membership.user_id).where(
                        Membership.user_id == user_id, Membership.team_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            if member is None:
                return None
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
        query = select(User).options(selectinload(User.team)).order_by(User.email)
        tenant_id = tenant_id_ctx.get()
        if tenant_id is not None:
            query = query.join(Membership, Membership.user_id == User.id).where(
                Membership.team_id == tenant_id
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_till_with_null_default(self) -> list[User]:
        result = await self.db.execute(
            select(User).where(
                User.role == UserRole.TILL,
                User.default_location_id.is_(None),
                User.team_id == tenant_id_ctx.get(),
            )
        )
        return list(result.scalars().all())
