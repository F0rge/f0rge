from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.quote import QuoteCRUD
from app.crud.sku import SkuCRUD
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.schemas.page import Page, PageParams
from app.schemas.quote import (
    QuoteAccept,
    QuoteCreate,
    QuoteLineCreate,
    QuoteLineResponse,
    QuoteListItem,
    QuoteResponse,
    QuoteUpdate,
)
from app.services.invoice_pdf import build_tax_invoice_pdf
from app.services.pricing import resolve_unit_ex_vat
from app.services.settings import SettingsService
from app.services.vat import CENT, ex_to_inc, inc_to_ex
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work


class QuotesService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = QuoteCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.sku_crud = SkuCRUD(db)

    async def list(
        self,
        params: PageParams,
        status: Optional[QuoteStatus] = None,
    ) -> Page[QuoteListItem]:
        rows, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            status=status,
        )
        return Page(items=[self._to_list_item(row) for row in rows], total=total)

    async def get(self, quote_id: uuid.UUID) -> QuoteResponse:
        return self._to_response(await self._get_or_404(quote_id))

    async def create(self, data: QuoteCreate, user_id: uuid.UUID) -> QuoteResponse:
        customer = await self._require_customer(data.customer_id)
        line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
            customer,
            data.lines,
        )
        quote = Quote(
            quote_number="",
            customer_id=customer.id,
            status=QuoteStatus.DRAFT,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            notes=data.notes,
            created_by_user_id=user_id,
            lines=line_models,
        )
        async with unit_of_work(self.db):
            quote.quote_number = await self.crud.get_next_quote_number()
            await self.crud.add_and_flush(quote)
        return self._to_response(await self._get_or_404(quote.id))

    async def create_from_snapshots(
        self,
        *,
        customer_id: uuid.UUID,
        user_id: uuid.UUID,
        notes: str,
        lines: list[tuple[uuid.UUID, int, Decimal, str]],
    ) -> QuoteResponse:
        customer = await self._require_customer(customer_id)
        models: list[QuoteLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        for sku_id, qty, unit_inc, description in lines:
            sku = await self.sku_crud.get_by_id(sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            unit_ex = inc_to_ex(unit_inc)
            ex_vat = (Decimal(qty) * unit_ex).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = (Decimal(qty) * unit_inc).quantize(CENT, rounding=ROUND_HALF_UP)
            vat_total += inc_vat - ex_vat
            subtotal += ex_vat
            total_inc += inc_vat
            models.append(
                QuoteLine(
                    sku_id=sku.id,
                    qty=qty,
                    unit_ex_vat=unit_ex,
                    description=description,
                    notes=None,
                )
            )
        quote = Quote(
            quote_number="",
            customer_id=customer.id,
            status=QuoteStatus.DRAFT,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_total,
            total_inc_vat=total_inc,
            notes=notes,
            created_by_user_id=user_id,
            lines=models,
        )
        async with unit_of_work(self.db):
            quote.quote_number = await self.crud.get_next_quote_number()
            await self.crud.add_and_flush(quote)
        return self._to_response(await self._get_or_404(quote.id))

    async def update(self, quote_id: uuid.UUID, data: QuoteUpdate) -> QuoteResponse:
        quote = await self._get_or_404(quote_id)
        if quote.status != QuoteStatus.DRAFT:
            raise ConflictError("Quote is not a draft")
        customer = quote.customer
        if data.customer_id is not None:
            customer = await self._require_customer(data.customer_id)
            quote.customer_id = customer.id
        if data.notes is not None:
            quote.notes = data.notes
        if data.lines is not None:
            line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
                customer,
                data.lines,
            )
            quote.lines.clear()
            await self.db.flush()
            quote.lines.extend(line_models)
            quote.subtotal_ex_vat = subtotal
            quote.vat_amount = vat_amount
            quote.total_inc_vat = total_inc
        await self.crud.commit_refresh(quote)
        return self._to_response(await self._get_or_404(quote.id))

    async def mark_sent(self, quote_id: uuid.UUID) -> QuoteResponse:
        quote = await self._get_or_404(quote_id)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            raise ConflictError("Quote cannot be marked sent")
        async with unit_of_work(self.db):
            quote.status = QuoteStatus.SENT
        return self._to_response(await self._get_or_404(quote.id))

    async def cancel(self, quote_id: uuid.UUID) -> QuoteResponse:
        quote = await self._get_or_404(quote_id)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            raise ConflictError("Quote cannot be cancelled")
        async with unit_of_work(self.db):
            quote.status = QuoteStatus.CANCELLED
        return self._to_response(await self._get_or_404(quote.id))

    async def serve_pdf(self, quote_id: uuid.UUID) -> Response:
        quote = await self._get_or_404(quote_id)
        seller = await SettingsService(self.db).build_seller_details()
        lines = []
        for line in quote.lines:
            ex_vat = (Decimal(line.qty) * line.unit_ex_vat).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            lines.append(
                (
                    line.description,
                    line.qty,
                    f"{line.unit_ex_vat:.2f}",
                    f"{ex_vat:.2f}",
                    f"{line_vat:.2f}",
                    f"{inc_vat:.2f}",
                )
            )
        pdf_bytes = build_tax_invoice_pdf(
            quote.quote_number,
            quote.created_at.date().isoformat(),
            quote.customer.name,
            quote.customer.vat_number,
            quote.customer.billing_address,
            lines,
            f"{quote.subtotal_ex_vat:.2f}",
            f"{quote.vat_amount:.2f}",
            f"{quote.total_inc_vat:.2f}",
            title="Quote",
            number_label="Quote No",
            seller=seller,
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def accept(self, quote_id: uuid.UUID, data: QuoteAccept, user_id: uuid.UUID):
        from app.services.sales_orders import SalesOrdersService

        quote = await self._get_or_404(quote_id)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            raise ConflictError("Quote cannot be accepted")
        return await SalesOrdersService(self.db).create_from_quote(quote, data, user_id)

    async def _require_customer(self, customer_id: uuid.UUID):
        customer = await self.customer_crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer

    async def _build_line_models(
        self,
        customer,
        lines: list[QuoteLineCreate],
    ) -> tuple[list[QuoteLine], Decimal, Decimal, Decimal]:
        models: list[QuoteLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        for line in lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            unit_ex = await resolve_unit_ex_vat(self.db, sku, customer)
            ex_vat = (Decimal(line.qty) * unit_ex).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            models.append(
                QuoteLine(
                    sku_id=sku.id,
                    qty=line.qty,
                    unit_ex_vat=unit_ex,
                    description=sku.name,
                    notes=line.notes,
                )
            )
        return models, subtotal, vat_total, total_inc

    async def _get_or_404(self, quote_id: uuid.UUID) -> Quote:
        quote = await self.crud.get_by_id(quote_id)
        if quote is None:
            raise NotFoundError("Quote not found")
        return quote

    @staticmethod
    def _items_label(quote: Quote) -> str:
        if not quote.lines:
            return "—"
        first = quote.lines[0]
        base = f"{first.sku.our_ref} — {first.description}"
        if len(quote.lines) == 1:
            return base
        return f"{base} +{len(quote.lines) - 1}"

    def _to_list_item(self, quote: Quote) -> QuoteListItem:
        return QuoteListItem(
            id=quote.id,
            quote_number=quote.quote_number,
            customer_id=quote.customer_id,
            customer_name=quote.customer.name,
            status=quote.status,
            subtotal_ex_vat=quote.subtotal_ex_vat,
            vat_amount=quote.vat_amount,
            total_inc_vat=quote.total_inc_vat,
            notes=quote.notes,
            items_label=self._items_label(quote),
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )

    def _to_response(self, quote: Quote) -> QuoteResponse:
        return QuoteResponse(
            id=quote.id,
            quote_number=quote.quote_number,
            customer_id=quote.customer_id,
            customer_name=quote.customer.name,
            status=quote.status,
            subtotal_ex_vat=quote.subtotal_ex_vat,
            vat_amount=quote.vat_amount,
            total_inc_vat=quote.total_inc_vat,
            notes=quote.notes,
            lines=[
                QuoteLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    our_ref=line.sku.our_ref,
                    name=line.sku.name,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    description=line.description,
                    notes=line.notes,
                )
                for line in quote.lines
            ],
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )
