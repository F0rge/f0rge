from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.layby import Layby, LaybyStatus
from app.models.tax_invoice import TaxInvoice
from f0rge_db.crud import BaseCRUD


@dataclass(frozen=True)
class CustomerInvoiceAgg:
    open_count: int = 0
    open_zar: Decimal = Decimal("0")
    overdue_count: int = 0


@dataclass(frozen=True)
class CustomerLaybyAgg:
    active_count: int = 0
    active_zar: Decimal = Decimal("0")


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

    async def invoice_aggregates_for_customers(
        self,
        customer_ids: list[uuid.UUID],
        as_of: datetime.date,
    ) -> dict[uuid.UUID, CustomerInvoiceAgg]:
        if not customer_ids:
            return {}

        overdue_cutoff = as_of - datetime.timedelta(days=30)
        balance = TaxInvoice.total_inc_vat - TaxInvoice.amount_paid
        stmt = (
            select(
                TaxInvoice.customer_id,
                func.count().filter(balance > 0).label("open_count"),
                func.coalesce(
                    func.sum(case((balance > 0, balance), else_=Decimal("0"))),
                    Decimal("0"),
                ).label("open_zar"),
                func.count()
                .filter(and_(balance > 0, TaxInvoice.issue_date <= overdue_cutoff))
                .label("overdue_count"),
            )
            .where(TaxInvoice.customer_id.in_(customer_ids))
            .group_by(TaxInvoice.customer_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {
            row.customer_id: CustomerInvoiceAgg(
                open_count=int(row.open_count),
                open_zar=Decimal(row.open_zar),
                overdue_count=int(row.overdue_count),
            )
            for row in rows
        }

    async def layby_aggregates_for_customers(
        self,
        customer_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, CustomerLaybyAgg]:
        if not customer_ids:
            return {}

        active_statuses = (LaybyStatus.OPEN, LaybyStatus.READY)
        balance = Layby.total_inc_vat - Layby.amount_paid
        stmt = (
            select(
                Layby.customer_id,
                func.count().filter(Layby.status.in_(active_statuses)).label("active_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (Layby.status.in_(active_statuses), balance),
                            else_=Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                ).label("active_zar"),
            )
            .where(Layby.customer_id.in_(customer_ids))
            .group_by(Layby.customer_id)
        )
        rows = (await self.db.execute(stmt)).all()
        return {
            row.customer_id: CustomerLaybyAgg(
                active_count=int(row.active_count),
                active_zar=Decimal(row.active_zar),
            )
            for row in rows
        }
