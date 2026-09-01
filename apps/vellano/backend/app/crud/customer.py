from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from f0rge_db.crud import BaseCRUD


class CustomerCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, customer_id: uuid.UUID) -> Optional[Customer]:
        return (
            await self.db.execute(select(Customer).where(Customer.id == customer_id))
        ).scalar_one_or_none()

    async def list_all(self) -> list[Customer]:
        result = await self.db.execute(select(Customer).order_by(Customer.name))
        return list(result.scalars().all())
