from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.customer import Customer
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class TaxInvoiceCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, invoice_id: uuid.UUID) -> Optional[TaxInvoice]:
        return (
            await self.db.execute(
                select(TaxInvoice)
                .options(
                    selectinload(TaxInvoice.customer),
                    selectinload(TaxInvoice.lines),
                )
                .where(TaxInvoice.id == invoice_id)
            )
        ).scalar_one_or_none()

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.lines),
            )
            .where(TaxInvoice.customer_id == customer_id)
            .order_by(TaxInvoice.invoice_number)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[TaxInvoice]:
        result = await self.db.execute(
            select(TaxInvoice)
            .options(
                selectinload(TaxInvoice.customer),
                selectinload(TaxInvoice.lines),
            )
            .order_by(TaxInvoice.invoice_number)
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[TaxInvoice], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    TaxInvoice.invoice_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                )
            )
        count_stmt = select(func.count(TaxInvoice.id)).join(
            Customer, TaxInvoice.customer_id == Customer.id
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(TaxInvoice)
            .options(selectinload(TaxInvoice.customer))
            .join(Customer, TaxInvoice.customer_id == Customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(
            TaxInvoice.issue_date.desc(),
            TaxInvoice.invoice_number.desc(),
        ).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_invoice_number(self) -> str:
        result = await self.db.execute(
            select(TaxInvoice.invoice_number).order_by(TaxInvoice.invoice_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "INV-0001"
        num = int(last.split("-")[1]) + 1
        return f"INV-{num:04d}"
