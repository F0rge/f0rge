from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bill import Bill
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.supplier import Supplier
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class PaymentCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(self, payment_id: uuid.UUID) -> Optional[Payment]:
        return (
            await self.db.execute(
                select(Payment)
                .options(
                    selectinload(Payment.invoice),
                    selectinload(Payment.bill),
                )
                .where(Payment.id == payment_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Payment]:
        result = await self.db.execute(
            select(Payment)
            .options(
                selectinload(Payment.invoice),
                selectinload(Payment.bill),
            )
            .order_by(Payment.payment_number)
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
    ) -> tuple[list[Payment], int]:
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Payment.payment_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                    Supplier.name.ilike(pattern),
                )
            )
        count_stmt = (
            select(func.count(Payment.id))
            .select_from(Payment)
            .outerjoin(TaxInvoice, Payment.invoice_id == TaxInvoice.id)
            .outerjoin(Customer, TaxInvoice.customer_id == Customer.id)
            .outerjoin(Bill, Payment.bill_id == Bill.id)
            .outerjoin(Supplier, Bill.supplier_id == Supplier.id)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = select(Payment).options(
            selectinload(Payment.invoice),
            selectinload(Payment.bill),
        )
        if q:
            stmt = (
                stmt.outerjoin(TaxInvoice, Payment.invoice_id == TaxInvoice.id)
                .outerjoin(Customer, TaxInvoice.customer_id == Customer.id)
                .outerjoin(Bill, Payment.bill_id == Bill.id)
                .outerjoin(Supplier, Bill.supplier_id == Supplier.id)
                .where(*filters)
            )
        stmt = (
            stmt.order_by(Payment.paid_on.desc(), Payment.payment_number.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_next_payment_number(self) -> str:
        result = await self.db.execute(
            select(Payment.payment_number).order_by(Payment.payment_number.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            return "PAY-0001"
        num = int(last.split("-")[1]) + 1
        return f"PAY-{num:04d}"
