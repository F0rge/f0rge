from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.sales_order import (
    SalesOrder,
    SalesOrderLine,
    SalesOrderStatus,
)
from f0rge_db.crud import BaseCRUD


class SalesOrderCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _options(self) -> tuple:
        return (
            selectinload(SalesOrder.customer),
            selectinload(SalesOrder.location),
            selectinload(SalesOrder.lines).selectinload(SalesOrderLine.sku),
            selectinload(SalesOrder.payments),
        )

    async def get_by_id(self, sales_order_id: uuid.UUID) -> Optional[SalesOrder]:
        return (
            await self.db.execute(
                select(SalesOrder).options(*self._options()).where(SalesOrder.id == sales_order_id)
            )
        ).scalar_one_or_none()

    async def get_line_by_id(self, line_id: uuid.UUID) -> Optional[SalesOrderLine]:
        return (
            await self.db.execute(
                select(SalesOrderLine)
                .options(
                    selectinload(SalesOrderLine.sku),
                    selectinload(SalesOrderLine.sales_order).selectinload(SalesOrder.customer),
                )
                .where(SalesOrderLine.id == line_id)
            )
        ).scalar_one_or_none()

    async def get_by_quote_id(self, quote_id: uuid.UUID) -> Optional[SalesOrder]:
        return (
            await self.db.execute(
                select(SalesOrder).options(*self._options()).where(SalesOrder.quote_id == quote_id)
            )
        ).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[SalesOrder]:
        result = await self.db.execute(
            select(SalesOrder)
            .options(*self._options())
            .where(SalesOrder.customer_id == customer_id)
            .order_by(SalesOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[SalesOrderStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[SalesOrder], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    SalesOrder.so_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(SalesOrder.status == status)
        if customer_id is not None:
            filters.append(SalesOrder.customer_id == customer_id)

        count_stmt = select(func.count(SalesOrder.id)).join(
            Customer, SalesOrder.customer_id == Customer.id
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(SalesOrder)
            .options(*self._options())
            .join(Customer, SalesOrder.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(SalesOrder.created_at.desc(), SalesOrder.so_number.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_so_number(self) -> str:
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("sales_order")
