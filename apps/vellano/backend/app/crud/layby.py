from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.layby import Layby, LaybyLine, LaybyStatus
from f0rge_db.crud import BaseCRUD


class LaybyCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, layby_id: uuid.UUID) -> Optional[Layby]:
        return (
            await self.db.execute(
                select(Layby)
                .options(
                    selectinload(Layby.customer),
                    selectinload(Layby.location),
                    selectinload(Layby.lines).selectinload(LaybyLine.sku),
                    selectinload(Layby.payments),
                )
                .where(Layby.id == layby_id)
            )
        ).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[Layby]:
        result = await self.db.execute(
            select(Layby)
            .options(
                selectinload(Layby.customer),
                selectinload(Layby.location),
                selectinload(Layby.lines).selectinload(LaybyLine.sku),
                selectinload(Layby.payments),
            )
            .where(Layby.customer_id == customer_id)
            .order_by(Layby.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Layby]:
        result = await self.db.execute(
            select(Layby)
            .options(
                selectinload(Layby.customer),
                selectinload(Layby.location),
                selectinload(Layby.lines).selectinload(LaybyLine.sku),
                selectinload(Layby.payments),
            )
            .order_by(Layby.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[LaybyStatus] = None,
    ) -> tuple[list[Layby], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Layby.layby_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(Layby.status == status)

        count_stmt = select(func.count(Layby.id)).join(Customer, Layby.customer_id == Customer.id)
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(Layby)
            .options(
                selectinload(Layby.customer),
                selectinload(Layby.location),
                selectinload(Layby.lines).selectinload(LaybyLine.sku),
            )
            .join(Customer, Layby.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(Layby.created_at.desc(), Layby.layby_number.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_layby_number(self) -> str:
        result = await self.db.execute(
            select(Layby.layby_number).order_by(Layby.layby_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "LB-0001"
        num = int(last.split("-")[1]) + 1
        return f"LB-{num:04d}"
