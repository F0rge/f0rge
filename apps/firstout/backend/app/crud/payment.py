from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.bill import Bill
from app.models.customer import Customer
from app.models.payment import Payment, PaymentDirection
from app.models.supplier import Supplier
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD

# Party and document number are shown with every payment.
_DOCUMENTS = (
    selectinload(Payment.invoice).selectinload(TaxInvoice.customer),
    selectinload(Payment.bill).selectinload(Bill.supplier),
)


class PaymentCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def get_by_id(
        self, payment_id: uuid.UUID, *, for_update: bool = False
    ) -> Optional[Payment]:
        stmt = select(Payment).options(*_DOCUMENTS).where(Payment.id == payment_id)
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> list[Payment]:
        result = await self.db.execute(
            select(Payment).options(*_DOCUMENTS).order_by(Payment.payment_number)
        )
        return list(result.scalars().all())

    async def summary(
        self, start: datetime.date, end: datetime.date
    ) -> tuple[dict[PaymentDirection, tuple[int, Decimal]], int, Decimal]:
        """Live (unvoided) totals paid in ``[start, end)`` per direction, and unreconciled."""
        live = Payment.voided_at.is_(None)
        month = await self.db.execute(
            select(Payment.direction, func.count(), func.coalesce(func.sum(Payment.amount_zar), 0))
            .where(live, Payment.paid_on >= start, Payment.paid_on < end)
            .group_by(Payment.direction)
        )
        signed = case(
            (Payment.direction == PaymentDirection.IN, Payment.amount_zar),
            else_=-Payment.amount_zar,
        )
        count, net = (
            await self.db.execute(
                select(func.count(), func.coalesce(func.sum(signed), 0)).where(
                    live, Payment.is_reconciled.is_(False)
                )
            )
        ).one()
        return {row[0]: (row[1], row[2]) for row in month.all()}, count, net

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        invoice_id: Optional[uuid.UUID] = None,
        bill_id: Optional[uuid.UUID] = None,
    ) -> tuple[list[Payment], int]:
        filters = []
        if invoice_id is not None:
            filters.append(Payment.invoice_id == invoice_id)
        if bill_id is not None:
            filters.append(Payment.bill_id == bill_id)
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

        stmt = select(Payment).options(*_DOCUMENTS)
        if q or invoice_id is not None or bill_id is not None:
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
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("payment")
