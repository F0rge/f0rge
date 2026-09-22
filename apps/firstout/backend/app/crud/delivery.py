from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.customer import Customer
from app.models.delivery import Delivery, DeliveryLine, DeliveryStatus
from app.models.layby import Layby
from app.models.sales_order import SalesOrder
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


class DeliveryCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    def _options(self) -> tuple:
        return (
            selectinload(Delivery.invoice).selectinload(TaxInvoice.customer),
            selectinload(Delivery.layby).selectinload(Layby.customer),
            selectinload(Delivery.sales_order).selectinload(SalesOrder.customer),
            selectinload(Delivery.location),
            selectinload(Delivery.lines).selectinload(DeliveryLine.sku),
        )

    async def get_by_id(self, delivery_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).options(*self._options()).where(Delivery.id == delivery_id)
            )
        ).scalar_one_or_none()

    async def list_all(self) -> list[Delivery]:
        result = await self.db.execute(
            select(Delivery).options(*self._options()).order_by(Delivery.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[DeliveryStatus] = None,
    ) -> tuple[list[Delivery], int]:
        invoice_customer = aliased(Customer)
        layby_customer = aliased(Customer)
        so_customer = aliased(Customer)
        filters = []
        if q:
            pattern = f"%{q}%"
            filters.append(
                or_(
                    Delivery.delivery_number.ilike(pattern),
                    invoice_customer.name.ilike(pattern),
                    layby_customer.name.ilike(pattern),
                    so_customer.name.ilike(pattern),
                )
            )
        if status is not None:
            filters.append(Delivery.status == status)

        count_stmt = (
            select(func.count(Delivery.id))
            .select_from(Delivery)
            .outerjoin(TaxInvoice, Delivery.invoice_id == TaxInvoice.id)
            .outerjoin(invoice_customer, TaxInvoice.customer_id == invoice_customer.id)
            .outerjoin(Layby, Delivery.layby_id == Layby.id)
            .outerjoin(layby_customer, Layby.customer_id == layby_customer.id)
            .outerjoin(SalesOrder, Delivery.sales_order_id == SalesOrder.id)
            .outerjoin(so_customer, SalesOrder.customer_id == so_customer.id)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(Delivery)
            .options(
                selectinload(Delivery.invoice).selectinload(TaxInvoice.customer),
                selectinload(Delivery.layby).selectinload(Layby.customer),
                selectinload(Delivery.sales_order).selectinload(SalesOrder.customer),
                selectinload(Delivery.location),
            )
            .outerjoin(TaxInvoice, Delivery.invoice_id == TaxInvoice.id)
            .outerjoin(invoice_customer, TaxInvoice.customer_id == invoice_customer.id)
            .outerjoin(Layby, Delivery.layby_id == Layby.id)
            .outerjoin(layby_customer, Layby.customer_id == layby_customer.id)
            .outerjoin(SalesOrder, Delivery.sales_order_id == SalesOrder.id)
            .outerjoin(so_customer, SalesOrder.customer_id == so_customer.id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = (
            stmt.order_by(
                Delivery.created_at.desc(),
                Delivery.delivery_number.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all()), total

    async def get_active_by_invoice_id(self, invoice_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).where(
                    Delivery.invoice_id == invoice_id,
                    Delivery.status != DeliveryStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_active_by_layby_id(self, layby_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).where(
                    Delivery.layby_id == layby_id,
                    Delivery.status != DeliveryStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_active_by_sales_order_id(self, sales_order_id: uuid.UUID) -> Optional[Delivery]:
        return (
            await self.db.execute(
                select(Delivery).where(
                    Delivery.sales_order_id == sales_order_id,
                    Delivery.status != DeliveryStatus.CANCELLED,
                )
            )
        ).scalar_one_or_none()

    async def get_next_delivery_number(self) -> str:
        from app.services.document_numbering import DocumentNumberingService

        return await DocumentNumberingService(self.db).allocate("delivery")
