from __future__ import annotations

from app.services.staff_identity import staff_identity_ctx

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.services.party_archive import assert_customer_active
from app.services.sellability import assert_sku_sellable
from app.services.sku_archive import SkuArchiveService
from app.crud.quote import QuoteCRUD
from app.crud.sku import SkuCRUD
from app.crud.user import UserCRUD
from app.exceptions import ForbiddenError
from app.crud.price_list import PriceListCRUD
from app.models.quote import OPEN_QUOTE_STATUSES, Quote, QuoteLine, QuoteStatus
from app.models.sales_staff import SalesStaff
from app.models.tax_invoice import TaxInvoice
from app.models.user import UserRole
from app.schemas.page import Page, PageParams
from app.schemas.quote import (
    QuoteAccept,
    QuoteCreate,
    QuoteLineCreate,
    QuoteLineResponse,
    QuoteListItem,
    QuotePreviewRequest,
    QuoteReplace,
    QuoteResponse,
    QuoteUpdate,
)
from app.schemas.till import TillPriceLine, TillPricePreview
from app.services.document_pdf import DocumentData, DocumentLine, DocumentParty
from app.services.pricing import (
    classification_of,
    format_pdf_unit,
    is_cin7_generated_price_list,
    pdf_unit_basis_note,
    pdf_unit_header,
    resolve_unit_price,
    shows_prices_including_vat,
)
from app.services.sales_staff import SalesStaffService
from app.services.settings import SettingsService
from app.services.suspect_price import annotate_line_warnings
from app.services.vat import CENT, discounted_unit_ex, ex_to_inc, inc_to_ex
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

_DISCOUNT_ROLES = frozenset({UserRole.OWNER.value, UserRole.TILL.value, UserRole.WAREHOUSE.value})
QUOTE_VALID_DAYS = 14


def _line_amounts(qty: int, unit_ex_vat: Decimal, discount: Decimal) -> tuple[Decimal, Decimal]:
    """A quote line's ex- and inc-VAT totals after its discount."""
    charged_unit = discounted_unit_ex(unit_ex_vat, discount)
    ex_vat = (Decimal(qty) * charged_unit).quantize(CENT, rounding=ROUND_HALF_UP)
    return ex_vat, ex_to_inc(ex_vat)


def quote_state(quote: Quote, today: datetime.date) -> str:
    if quote.status in OPEN_QUOTE_STATUSES:
        expired = quote.status == QuoteStatus.EXPIRED or (
            quote.valid_until is not None and quote.valid_until < today
        )
        return "expired" if expired else "open"
    return quote.status.value


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
        return Page(items=await self._items(rows), total=total)

    async def get_item(self, quote_id: uuid.UUID) -> QuoteListItem:
        return (await self._items([await self._get_or_404(quote_id)]))[0]

    async def list_all(self) -> list[QuoteListItem]:
        """Every quote, for the record workspace."""
        return await self._items(await self.crud.list_all())

    async def get(
        self,
        quote_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        return await self._to_response(await self._get_or_404(quote_id), viewer_user_id)

    async def create(self, data: QuoteCreate, user_id: uuid.UUID) -> QuoteResponse:
        quote = await self.prepare_draft(data, user_id)
        async with unit_of_work(self.db):
            await self.stage_draft(quote)
        return await self._to_response(await self._get_or_404(quote.id), user_id)

    async def prepare_draft(self, data: QuoteCreate, user_id: uuid.UUID) -> Quote:
        customer = await self._require_customer(data.customer_id)
        assert_customer_active(customer)
        if data.sales_staff_id is not None:
            await SalesStaffService(self.db).check_sale_colleague(data.sales_staff_id)
        role = await self._actor_role(user_id)
        line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
            customer,
            data.lines,
            allow_price_override=role == UserRole.OWNER.value,
            allow_discount=role in _DISCOUNT_ROLES,
        )
        return Quote(
            quote_number="",
            customer_id=customer.id,
            status=QuoteStatus.DRAFT,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            notes=data.notes,
            internal_note=data.internal_note,
            valid_until=data.valid_until
            or datetime.date.today() + datetime.timedelta(days=QUOTE_VALID_DAYS),
            sales_staff_id=data.sales_staff_id,
            prices_include_vat=shows_prices_including_vat(customer),
            created_by_user_id=user_id,
            lines=line_models,
        )

    async def stage_draft(self, quote: Quote) -> None:
        quote.quote_number = await self.crud.get_next_quote_number()
        await self.crud.add_and_flush(quote)

    async def create_from_snapshots(
        self,
        *,
        customer_id: uuid.UUID,
        user_id: uuid.UUID,
        notes: str,
        lines: list[tuple[uuid.UUID, int, Decimal, str]],
    ) -> QuoteResponse:
        customer = await self._require_customer(customer_id)
        assert_customer_active(customer)
        await SkuArchiveService(self.db).lock_skus([line[0] for line in lines])
        models: list[QuoteLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        for sku_id, qty, unit_inc, description in lines:
            sku = await self.sku_crud.get_by_id(sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            assert_sku_sellable(sku)
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
        await SkuArchiveService(self.db).lock_skus([])
        quote = await self._get_or_404(quote_id)
        self._assert_open(quote, "edited")
        # PUT replaces the editor's fields; PATCH changes only those it sends.
        fields = (
            set(QuoteUpdate.model_fields)
            if isinstance(data, QuoteReplace)
            else data.model_fields_set
        )
        if "internal_note" in fields:
            quote.internal_note = data.internal_note
        if "valid_until" in fields:
            quote.valid_until = data.valid_until
        if "sales_staff_id" in fields and data.sales_staff_id != quote.sales_staff_id:
            if data.sales_staff_id is not None:
                await SalesStaffService(self.db).check_sale_colleague(data.sales_staff_id)
            quote.sales_staff_id = data.sales_staff_id
        if isinstance(data, QuoteReplace):
            quote.notes = data.notes
        customer = quote.customer
        if data.customer_id is not None:
            customer = await self._require_customer(data.customer_id)
            if data.customer_id != quote.customer_id:
                assert_customer_active(customer)
                await SkuArchiveService(self.db).lock_skus([line.sku_id for line in quote.lines])
                for line in quote.lines:
                    sku = await self.sku_crud.get_by_id(line.sku_id)
                    if sku is not None and sku.is_archived:
                        raise ValidationError(
                            f"Restore SKU {sku.our_ref} before assigning this quote to another customer"
                        )
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

    async def delete(self, quote_id: uuid.UUID) -> None:
        quote = await self._get_or_404(quote_id)
        if quote.status not in OPEN_QUOTE_STATUSES | {QuoteStatus.CANCELLED}:
            raise ConflictError(
                f"{quote.quote_number} is {quote.status.value}; it cannot be deleted"
            )
        async with unit_of_work(self.db):
            await self.db.delete(quote)

    async def preview(self, data: QuotePreviewRequest, user_id: uuid.UUID) -> TillPricePreview:
        """The cart's prices and totals exactly as saving it would store them."""
        customer = await self._require_customer(data.customer_id)
        previous: list[QuoteLine] = []
        if data.quote_id is not None:
            quote = await self._get_or_404(data.quote_id)
            previous = list(quote.lines)
        role = await self._actor_role(user_id)
        models, subtotal, vat_amount, total_inc = await self._build_line_models(
            customer,
            data.lines,
            allow_price_override=role == UserRole.OWNER.value,
            allow_discount=role in _DISCOUNT_ROLES,
            previous_lines=previous,
        )
        lines = []
        for model in models:
            ex_vat, inc_vat = _line_amounts(model.qty, model.unit_ex_vat, model.discount_percent)
            lines.append(
                TillPriceLine(
                    sku_id=model.sku_id,
                    qty=model.qty,
                    discount_percent=model.discount_percent,
                    unit_ex_vat=model.unit_ex_vat,
                    before_discount_ex_vat=model.unit_ex_vat * model.qty,
                    ex_vat=ex_vat,
                    vat_amount=inc_vat - ex_vat,
                    inc_vat=inc_vat,
                    source="quote",
                    price_warning=model.price_warning,
                )
            )
        price_list_name = None
        if customer.price_list_id is not None:
            policy = await PriceListCRUD(self.db).get_till_policy(customer.price_list_id)
            if policy is not None and not is_cin7_generated_price_list(policy[0]):
                price_list_name = policy[0]
        return TillPricePreview(
            classification=classification_of(customer),
            price_list_name=price_list_name,
            prices_include_vat=shows_prices_including_vat(customer),
            before_discount_ex_vat=sum((line.before_discount_ex_vat for line in lines), Decimal(0)),
            before_discount_inc_vat=sum(
                (ex_to_inc(line.before_discount_ex_vat) for line in lines), Decimal(0)
            ),
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            lines=lines,
            price_revision="",
        )

    async def lock_for_conversion(self, quote_id: uuid.UUID) -> Quote:
        """The open quote a till sale converts, locked until that sale commits."""
        quote = await self.db.scalar(
            select(Quote)
            .where(Quote.id == quote_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if quote is None:
            raise NotFoundError("Quote not found")
        self._assert_open(quote, "sold")
        return quote

    @staticmethod
    def _assert_open(quote: Quote, verb: str) -> None:
        if quote.status not in OPEN_QUOTE_STATUSES:
            raise ConflictError(
                f"{quote.quote_number} is {quote.status.value}; it cannot be {verb}"
            )

    async def document_data(self, quote_id: uuid.UUID) -> DocumentData:
        quote = await self._get_or_404(quote_id)
        lines = []
        for line in quote.lines:
            ex_vat, inc_vat = _line_amounts(line.qty, line.unit_ex_vat, line.discount_percent)
            description = line.description
            if line.price_warning:
                description = f"{description} — {line.price_warning}"
            sku = await self.sku_crud.get_by_id(line.sku_id)
            lines.append(
                DocumentLine(
                    description=description,
                    qty=str(line.qty),
                    unit=format_pdf_unit(line.unit_ex_vat, quote.prices_include_vat),
                    ex_vat=f"{ex_vat:.2f}",
                    vat=f"{inc_vat - ex_vat:.2f}",
                    inc_vat=f"{inc_vat:.2f}",
                    discount=f"{line.discount_percent:.2f}%" if line.discount_percent > 0 else None,
                    sku_ref=sku.our_ref if sku is not None else None,
                )
            )
        customer = quote.customer
        return DocumentData(
            kind="quote",
            number=quote.quote_number,
            issue_date=quote.created_at.date().isoformat(),
            details=[("Valid until", quote.valid_until.isoformat())] if quote.valid_until else [],
            served_by=await SalesStaffService(self.db).served_by(quote.sales_staff_id),
            party=DocumentParty(
                label="Prepared for",
                name=customer.name,
                address=customer.billing_address,
                vat_number=customer.vat_number,
            ),
            lines=lines,
            subtotal_ex_vat=f"{quote.subtotal_ex_vat:.2f}",
            vat_amount=f"{quote.vat_amount:.2f}",
            total=f"{quote.total_inc_vat:.2f}",
            unit_basis_note=pdf_unit_basis_note(quote.prices_include_vat),
            unit_header=pdf_unit_header(quote.prices_include_vat),
            # The printed note only; internal_note stays with staff.
            note=quote.notes,
            payment_reference=True,
        )

    async def serve_pdf(self, quote_id: uuid.UUID) -> Response:
        data = await self.document_data(quote_id)
        pdf_bytes = await SettingsService(self.db).render_document(data)
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
        identity = staff_identity_ctx.get()
        return identity.role if identity and identity.user_id == user.id else user.role

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
        await SkuArchiveService(self.db).lock_skus([line.sku_id for line in lines])
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
            if prior is None:
                assert_sku_sellable(sku)
            elif sku.is_archived and line.qty > prior.qty:
                raise ValidationError(
                    f"Restore SKU {sku.our_ref} before increasing an existing order quantity"
                )
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
            ex_vat, inc_vat = _line_amounts(line.qty, unit_ex, discount)
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

    async def _labels(
        self, quotes: list[Quote]
    ) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
        """Colleague names and converted invoice numbers for these quotes."""
        staff_ids = {quote.sales_staff_id for quote in quotes if quote.sales_staff_id}
        invoice_ids = {quote.converted_invoice_id for quote in quotes if quote.converted_invoice_id}
        staff = (
            dict(
                (
                    await self.db.execute(
                        select(SalesStaff.id, SalesStaff.name).where(SalesStaff.id.in_(staff_ids))
                    )
                ).all()
            )
            if staff_ids
            else {}
        )
        invoices = (
            dict(
                (
                    await self.db.execute(
                        select(TaxInvoice.id, TaxInvoice.invoice_number).where(
                            TaxInvoice.id.in_(invoice_ids)
                        )
                    )
                ).all()
            )
            if invoice_ids
            else {}
        )
        return staff, invoices

    async def _items(self, quotes: list[Quote]) -> list[QuoteListItem]:
        staff, invoices = await self._labels(quotes)
        today = datetime.date.today()
        return [self._to_list_item(quote, staff, invoices, today) for quote in quotes]

    def _to_list_item(
        self,
        quote: Quote,
        staff: dict[uuid.UUID, str],
        invoices: dict[uuid.UUID, str],
        today: datetime.date,
    ) -> QuoteListItem:
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
            sales_staff_id=quote.sales_staff_id,
            sales_staff_name=staff.get(quote.sales_staff_id) if quote.sales_staff_id else None,
            valid_until=quote.valid_until,
            issue_date=quote.created_at.date(),
            converted_invoice_id=quote.converted_invoice_id,
            converted_invoice_number=invoices.get(quote.converted_invoice_id)
            if quote.converted_invoice_id
            else None,
            is_converted=quote.status in (QuoteStatus.CONVERTED, QuoteStatus.ACCEPTED),
            state=quote_state(quote, today),
            item_count=sum(line.qty for line in quote.lines),
            items_label=self._items_label(quote),
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )

    async def _to_response(
        self,
        quote: Quote,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> QuoteResponse:
        _, invoices = await self._labels([quote])
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
            internal_note=quote.internal_note,
            sales_staff_id=quote.sales_staff_id,
            valid_until=quote.valid_until,
            issue_date=quote.created_at.date(),
            converted_invoice_id=quote.converted_invoice_id,
            converted_invoice_number=invoices.get(quote.converted_invoice_id)
            if quote.converted_invoice_id
            else None,
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
        await annotate_line_warnings(
            self.db,
            response.lines,
            viewer_user_id=viewer_user_id,
            prices_include_vat=quote.prices_include_vat,
        )
        return response
