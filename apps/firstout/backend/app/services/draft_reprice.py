"""Reprice draft quotes and draft sales orders after a confirmed classification change.

Issued invoices, sent quotes, and non-draft sales orders are left as they were.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.customer import CustomerCRUD
from app.crud.sku import SkuCRUD
from app.models.quote import Quote, QuoteStatus
from app.models.sales_order import SalesOrder, SalesOrderStatus
from app.services.pricing import shows_prices_including_vat
from app.services.sale_line_pricing import (
    PricingAuthority,
    SaleLinePricing,
    SaleLineRequest,
    document_totals,
)
from f0rge_core.exceptions import NotFoundError
from f0rge_db.crud import unit_of_work


@dataclass(frozen=True)
class DraftDocumentCounts:
    quotes: int
    sales_orders: int


class DraftRepriceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.customers = CustomerCRUD(db)
        self.skus = SkuCRUD(db)

    async def counts_for(self, customer_id: uuid.UUID) -> DraftDocumentCounts:
        quotes = await self.db.scalar(
            select(func.count())
            .select_from(Quote)
            .where(Quote.customer_id == customer_id, Quote.status == QuoteStatus.DRAFT)
        )
        orders = await self.db.scalar(
            select(func.count())
            .select_from(SalesOrder)
            .where(
                SalesOrder.customer_id == customer_id,
                SalesOrder.status == SalesOrderStatus.DRAFT,
            )
        )
        return DraftDocumentCounts(quotes=int(quotes or 0), sales_orders=int(orders or 0))

    async def reprice(self, customer_id: uuid.UUID) -> DraftDocumentCounts:
        customer = await self.customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        including_vat = shows_prices_including_vat(customer)

        quotes = (
            (
                await self.db.scalars(
                    select(Quote)
                    .where(Quote.customer_id == customer_id, Quote.status == QuoteStatus.DRAFT)
                    .options(selectinload(Quote.lines))
                )
            )
            .unique()
            .all()
        )
        orders = (
            (
                await self.db.scalars(
                    select(SalesOrder)
                    .where(
                        SalesOrder.customer_id == customer_id,
                        SalesOrder.status == SalesOrderStatus.DRAFT,
                    )
                    .options(selectinload(SalesOrder.lines))
                )
            )
            .unique()
            .all()
        )

        # The reprice is not a staff discount decision: each line keeps its discount and
        # takes the customer's new resolved price.
        pricing = await SaleLinePricing.for_customer(self.db, customer, PricingAuthority.system())
        async with unit_of_work(self.db):
            for document in [*quotes, *orders]:
                # A line stored before discounts were kept (NULL) has an already-net unit;
                # repricing it would drop a discount we cannot see, so it keeps its unit.
                lines = [line for line in document.lines if line.discount_percent is not None]
                requests = []
                for line in lines:
                    sku = await self.skus.get_by_id(line.sku_id)
                    if sku is None:
                        raise NotFoundError("SKU not found")
                    requests.append(
                        SaleLineRequest(
                            sku=sku, qty=line.qty, discount_percent=line.discount_percent
                        )
                    )
                priced = await pricing.price(requests)
                for line, price in zip(lines, priced.lines, strict=True):
                    line.unit_ex_vat = price.unit_ex_vat
                    line.price_warning = price.price_warning
                (
                    document.subtotal_ex_vat,
                    document.vat_amount,
                    document.total_inc_vat,
                ) = document_totals(
                    (
                        (line.unit_ex_vat, line.qty, line.discount_percent)
                        for line in document.lines
                    ),
                    # The draft keeps the rate it was created at (ADR 0003).
                    document.vat_rate,
                )
                document.prices_include_vat = including_vat

        return DraftDocumentCounts(quotes=len(quotes), sales_orders=len(orders))
