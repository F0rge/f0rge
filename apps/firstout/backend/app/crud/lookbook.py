from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.lookbook import Lookbook
from f0rge_db.crud import BaseCRUD


class LookbookCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _options(self):
        return (
            selectinload(Lookbook.customer),
            selectinload(Lookbook.items),
        )

    async def get_by_id(self, lookbook_id: uuid.UUID) -> Optional[Lookbook]:
        return (
            await self.db.execute(
                select(Lookbook).options(*self._options()).where(Lookbook.id == lookbook_id)
            )
        ).scalar_one_or_none()

    async def get_by_token(self, token: str) -> Optional[Lookbook]:
        return (
            await self.db.execute(
                select(Lookbook).options(*self._options()).where(Lookbook.token == token)
            )
        ).scalar_one_or_none()

    async def token_exists(self, token: str) -> bool:
        found = await self.db.scalar(select(Lookbook.id).where(Lookbook.token == token))
        return found is not None

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[Lookbook], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Lookbook.name.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )

        count_stmt = select(func.count(Lookbook.id)).outerjoin(
            Customer, Lookbook.customer_id == Customer.id
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(Lookbook)
            .options(*self._options())
            .outerjoin(Customer, Lookbook.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(Lookbook.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total
