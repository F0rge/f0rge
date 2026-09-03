from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.hypothesis import Hypothesis
from f0rge_db.tenant import owned_by_user


class HypothesisCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def list(self, status: Optional[str] = None) -> list[Hypothesis]:
        stmt = select(Hypothesis).where(owned_by_user(Hypothesis.user_id))
        if status is not None:
            stmt = stmt.where(Hypothesis.status == status)
        stmt = stmt.order_by(Hypothesis.sort_order.asc(), Hypothesis.created_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_id(self, hypothesis_id: uuid.UUID) -> Optional[Hypothesis]:
        stmt = select(Hypothesis).where(
            owned_by_user(Hypothesis.user_id),
            Hypothesis.id == hypothesis_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Hypothesis]:
        stmt = select(Hypothesis).where(
            owned_by_user(Hypothesis.user_id),
            Hypothesis.slug == slug,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
