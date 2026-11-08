"""Reprice draft quotes and draft sales orders after a confirmed classification change.

Issued invoices, sent quotes, and non-draft sales orders are left as they were.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.customer import CustomerCRUD
from app.crud.sku import SkuCRUD
from app.models.quote import Quote, QuoteStatus
from app.models.sales_order import SalesOrder, SalesOrderStatus
from app.services.pricing import resolve_unit_price, shows_prices_including_vat
from app.services.vat import CENT, discounted_unit_ex, ex_to_inc
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

        async with unit_of_work(self.db):
            for quote in quotes:
                for line in quote.lines:
                    sku = await self.skus.get_by_id(line.sku_id)
                    if sku is None:
                        raise NotFoundError("SKU not found")
                    resolved = await resolve_unit_price(self.db, sku, customer)
                    line.unit_ex_vat = resolved.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
                    line.price_warning = resolved.warning
                subtotal, vat_amount, total_inc = _quote_totals(quote.lines)
                quote.subtotal_ex_vat = subtotal
                quote.vat_amount = vat_amount
                quote.total_inc_vat = total_inc
                quote.prices_include_vat = including_vat

            for order in orders:
                subtotal = Decimal(0)
                vat_amount = Decimal(0)
                total_inc = Decimal(0)
                for line in order.lines:
                    sku = await self.skus.get_by_id(line.sku_id)
                    if sku is None:
                        raise NotFoundError("SKU not found")
                    resolved = await resolve_unit_price(self.db, sku, customer)
                    unit_ex = resolved.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
                    line.unit_ex_vat = unit_ex
                    line.price_warning = resolved.warning
                    ex_vat = (Decimal(line.qty) * unit_ex).quantize(CENT, rounding=ROUND_HALF_UP)
                    inc_vat = ex_to_inc(ex_vat)
                    subtotal += ex_vat
                    vat_amount += inc_vat - ex_vat
                    total_inc += inc_vat
                order.subtotal_ex_vat = subtotal
                order.vat_amount = vat_amount
                order.total_inc_vat = total_inc
                order.prices_include_vat = including_vat

        return DraftDocumentCounts(quotes=len(quotes), sales_orders=len(orders))


def _quote_totals(lines) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = Decimal(0)
    vat_amount = Decimal(0)
    total_inc = Decimal(0)
    for line in lines:
        charged = discounted_unit_ex(line.unit_ex_vat, line.discount_percent)
        ex_vat = (Decimal(line.qty) * charged).quantize(CENT, rounding=ROUND_HALF_UP)
        inc_vat = ex_to_inc(ex_vat)
        subtotal += ex_vat
        vat_amount += inc_vat - ex_vat
        total_inc += inc_vat
    return subtotal, vat_amount, total_inc
