from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.quote import QuoteCRUD
from app.crud.sku import SkuCRUD
from app.crud.user import UserCRUD
from app.exceptions import ForbiddenError
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.models.user import UserRole
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
from app.services.pricing import (
    format_pdf_unit,
    pdf_unit_basis_note,
    resolve_unit_price,
    shows_prices_including_vat,
)
from app.services.settings import SettingsService
from app.services.suspect_price import annotate_line_warnings
from app.services.vat import CENT, discounted_unit_ex, ex_to_inc, inc_to_ex
from f0rge_core.exceptions import ConflictError, NotFoundError
from f0rge_db.crud import unit_of_work

_DISCOUNT_ROLES = frozenset({UserRole.OWNER.value, UserRole.TILL.value, UserRole.WAREHOUSE.value})


class QuotesService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = QuoteCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.user_crud = UserCRUD(db)

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

    async def get(
        self,
        quote_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        return await self._to_response(await self._get_or_404(quote_id), viewer_user_id)

    async def create(self, data: QuoteCreate, user_id: uuid.UUID) -> QuoteResponse:
        customer = await self._require_customer(data.customer_id)
        role = await self._actor_role(user_id)
        line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
            customer,
            data.lines,
            allow_price_override=role == UserRole.OWNER.value,
            allow_discount=role in _DISCOUNT_ROLES,
        )
        quote = Quote(
            quote_number="",
            customer_id=customer.id,
            status=QuoteStatus.DRAFT,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            notes=data.notes,
            prices_include_vat=shows_prices_including_vat(customer),
            created_by_user_id=user_id,
            lines=line_models,
        )
        async with unit_of_work(self.db):
            quote.quote_number = await self.crud.get_next_quote_number()
            await self.crud.add_and_flush(quote)
        return await self._to_response(await self._get_or_404(quote.id), user_id)

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
                    discount_percent=Decimal(0),
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
            prices_include_vat=shows_prices_including_vat(customer),
            created_by_user_id=user_id,
            lines=models,
        )
        async with unit_of_work(self.db):
            quote.quote_number = await self.crud.get_next_quote_number()
            await self.crud.add_and_flush(quote)
        return await self._to_response(await self._get_or_404(quote.id), user_id)

    async def update(
        self,
        quote_id: uuid.UUID,
        data: QuoteUpdate,
        user_id: uuid.UUID,
    ) -> QuoteResponse:
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
            role = await self._actor_role(user_id)
            line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
                customer,
                data.lines,
                allow_price_override=role == UserRole.OWNER.value,
                allow_discount=role in _DISCOUNT_ROLES,
                previous_lines=list(quote.lines),
            )
            quote.lines.clear()
            await self.db.flush()
            quote.lines.extend(line_models)
            quote.subtotal_ex_vat = subtotal
            quote.vat_amount = vat_amount
            quote.total_inc_vat = total_inc
        await self.crud.commit_refresh(quote)
        return await self._to_response(await self._get_or_404(quote.id), user_id)

    async def mark_sent(
        self,
        quote_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        quote = await self._get_or_404(quote_id)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            raise ConflictError("Quote cannot be marked sent")
        async with unit_of_work(self.db):
            quote.status = QuoteStatus.SENT
        return await self._to_response(await self._get_or_404(quote.id), viewer_user_id)

    async def cancel(
        self,
        quote_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        quote = await self._get_or_404(quote_id)
        if quote.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            raise ConflictError("Quote cannot be cancelled")
        async with unit_of_work(self.db):
            quote.status = QuoteStatus.CANCELLED
        return await self._to_response(await self._get_or_404(quote.id), viewer_user_id)

    async def serve_pdf(self, quote_id: uuid.UUID) -> Response:
        quote = await self._get_or_404(quote_id)
        seller = await SettingsService(self.db).build_seller_details()
        lines = []
        for line in quote.lines:
            charged_unit = discounted_unit_ex(line.unit_ex_vat, line.discount_percent)
            ex_vat = (Decimal(line.qty) * charged_unit).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            description = line.description
            if line.discount_percent > 0:
                description = f"{description} ({line.discount_percent:.2f}% discount)"
            if line.price_warning:
                description = f"{description} — {line.price_warning}"
            lines.append(
                (
                    description,
                    line.qty,
                    format_pdf_unit(line.unit_ex_vat, quote.prices_include_vat),
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
            unit_basis_note=pdf_unit_basis_note(quote.prices_include_vat),
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

    async def _actor_role(self, user_id: uuid.UUID) -> str:
        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            return ""
        return user.role

    def _resolve_discount(
        self,
        sku,
        submitted: Decimal,
        previous: Decimal,
        allow_discount: bool,
    ) -> Decimal:
        submitted_q = submitted.quantize(CENT, rounding=ROUND_HALF_UP)
        previous_q = previous.quantize(CENT, rounding=ROUND_HALF_UP)
        if submitted_q == previous_q or allow_discount:
            return submitted_q
        raise ForbiddenError(
            f"Only the owner, till, or warehouse can change the discount for {sku.our_ref}"
        )

    async def _line_unit_ex_vat(
        self,
        sku,
        customer,
        line: QuoteLineCreate,
        allow_price_override: bool,
        previous_unit: Optional[Decimal],
        previous_warning: Optional[str],
    ) -> tuple[Decimal, Optional[str]]:
        resolved = await resolve_unit_price(self.db, sku, customer)
        computed = resolved.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
        if line.unit_ex_vat is None:
            if previous_unit is not None:
                return previous_unit.quantize(CENT, rounding=ROUND_HALF_UP), previous_warning
            return computed, resolved.warning
        submitted = line.unit_ex_vat.quantize(CENT, rounding=ROUND_HALF_UP)
        if submitted == computed or allow_price_override:
            warning = resolved.warning if submitted == computed else None
            return submitted, warning
        raise ForbiddenError(f"Only the owner can change the unit price for {sku.our_ref}")

    async def _build_line_models(
        self,
        customer,
        lines: list[QuoteLineCreate],
        *,
        allow_price_override: bool,
        allow_discount: bool,
        previous_lines: Optional[list[QuoteLine]] = None,
    ) -> tuple[list[QuoteLine], Decimal, Decimal, Decimal]:
        models: list[QuoteLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        unmatched = list(previous_lines or [])
        for line in lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            prior = next((row for row in unmatched if row.sku_id == sku.id), None)
            if prior is not None:
                unmatched.remove(prior)
            unit_ex, warning = await self._line_unit_ex_vat(
                sku,
                customer,
                line,
                allow_price_override,
                prior.unit_ex_vat if prior is not None else None,
                prior.price_warning if prior is not None else None,
            )
            discount = self._resolve_discount(
                sku,
                line.discount_percent,
                prior.discount_percent if prior is not None else Decimal(0),
                allow_discount,
            )
            charged_unit = discounted_unit_ex(unit_ex, discount)
            ex_vat = (Decimal(line.qty) * charged_unit).quantize(CENT, rounding=ROUND_HALF_UP)
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
                    discount_percent=discount,
                    description=sku.name,
                    notes=line.notes,
                    price_warning=warning,
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

    async def _to_response(
        self,
        quote: Quote,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        response = QuoteResponse(
            id=quote.id,
            quote_number=quote.quote_number,
            customer_id=quote.customer_id,
            customer_name=quote.customer.name,
            status=quote.status,
            subtotal_ex_vat=quote.subtotal_ex_vat,
            vat_amount=quote.vat_amount,
            total_inc_vat=quote.total_inc_vat,
            notes=quote.notes,
            prices_include_vat=quote.prices_include_vat,
            lines=[
                QuoteLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    our_ref=line.sku.our_ref,
                    name=line.sku.name,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    discount_percent=line.discount_percent,
                    description=line.description,
                    notes=line.notes,
                    price_warning=line.price_warning,
                )
                for line in quote.lines
            ],
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )
        await annotate_line_warnings(self.db, response.lines, viewer_user_id=viewer_user_id)
        return response
