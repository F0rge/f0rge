from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from f0rge_db.crud import unit_of_work

WALK_IN_CUSTOMER_NAME = "Walk-in customer"


class TillSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def seed_if_empty(self) -> None:
        existing = (
            await self.db.execute(
                select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return

        async with unit_of_work(self.db):
            customer = Customer(name=WALK_IN_CUSTOMER_NAME)
            self.db.add(customer)
            await self.db.flush()
