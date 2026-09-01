from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.role import Role
from app.models.user import User, UserRole
from f0rge_db.crud import BaseCRUD


class RoleCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, role_id: uuid.UUID) -> Optional[Role]:
        return (
            await self.db.execute(
                select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
            )
        ).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Role]:
        return (
            await self.db.execute(
                select(Role).options(selectinload(Role.permissions)).where(Role.slug == slug)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Role]:
        result = await self.db.execute(
            select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        )
        return list(result.scalars().all())

    async def list_owner_slugs(self) -> list[str]:
        result = await self.db.execute(select(Role.slug).where(Role.is_owner_preset.is_(True)))
        slugs = list(result.scalars().all())
        if UserRole.OWNER.value not in slugs:
            slugs.append(UserRole.OWNER.value)
        return slugs

    async def count_users_with_slugs(self, slugs: list[str], *, active_only: bool = True) -> int:
        stmt = select(func.count()).select_from(User).where(User.role.in_(slugs))
        if active_only:
            stmt = stmt.where(User.is_disabled.is_(False))
        return int((await self.db.execute(stmt)).scalar_one())

    async def count_users_with_slug(self, slug: str) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.role == slug)
        )
        return int(result.scalar_one())
