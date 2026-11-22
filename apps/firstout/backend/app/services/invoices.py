from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.customer import CustomerCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.sales_staff import SalesStaff
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceLineResponse,
    InvoiceListItem,
    InvoicePaymentCreate,
    InvoicePreviewRequest,
    InvoiceSummary,
    InvoiceUpdate,
    InvoiceResponse,
    ManualInvoiceCreate,
)
from app.schemas.page import Page, PageParams
from app.schemas.payment import PaymentCreate
from app.schemas.sale_line_pricing import SalePricePreview
from app.services.books_events import BooksEventService
from app.services.customer_credit import CustomerCreditService
from app.services.document_pdf import DocumentData, DocumentLine, DocumentParty
from app.services.party_archive import require_active_customer
from app.services.sellability import assert_sku_sellable
from app.services.sku_archive import SkuArchiveService
from app.services.archive_documents import assert_operational_document
from app.services.payments import PaymentService
from app.services.pricing import (
    customer_price_warning,
    format_pdf_discount,
    format_pdf_unit,
    pdf_unit_basis_note,
    pdf_unit_header,
    shows_prices_including_vat,
)
from app.services.suspect_price import annotate_line_warnings
from app.services.sales_staff import SalesStaffService
from app.services.settings import SettingsService
from app.services.settlement import SettlementStatus, cents
from app.services.sale_line_pricing import PricingAuthority, SaleLinePricing, SaleLineRequest
from app.services.tax_invoice_issue import TaxInvoiceIssue
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TaxInvoiceCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.events = BooksEventService(db)
        self.credit = CustomerCreditService(db)

    async def list(self, params: PageParams) -> Page[InvoiceListItem]:
        invoices, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
        )
        names = await self._staff_names()
        return Page(
            items=[self._to_list_item(invoice, names) for invoice in invoices],
            total=total,
        )

    async def list_all(self) -> list[InvoiceListItem]:
        """Every invoice for the workspace, Cin7 imports and archived ones included."""
        invoices = (
            await self.db.execute(
                select(TaxInvoice)
                .options(selectinload(TaxInvoice.customer))
                .order_by(TaxInvoice.invoice_number)
            )
        ).scalars()
        names = await self._staff_names()
        return [self._to_list_item(invoice, names) for invoice in invoices]

    async def get_list_item(self, invoice_id: uuid.UUID) -> InvoiceListItem:
        invoice = await self.crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        return self._to_list_item(invoice, await self._staff_names())

    async def summary(self) -> InvoiceSummary:
        # The statuses of _lifecycle_fields, in SQL. Archived invoices are still owed;
        # only Cin7 imports carry no balance.
        balance = func.round(TaxInvoice.total_inc_vat - TaxInvoice.amount_paid, 2)
        overdue = and_(
            TaxInvoice.payment_status != SettlementStatus.PAID,
            TaxInvoice.due_date < datetime.date.today(),
        )
        statement = and_(
            TaxInvoice.payment_status == SettlementStatus.UNPAID,
            TaxInvoice.on_account,
            or_(TaxInvoice.due_date.is_(None), TaxInvoice.due_date >= datetime.date.today()),
        )

        def bucket(condition):
            return func.coalesce(func.sum(balance).filter(condition), 0), func.count().filter(
                condition
            )

        owing_zar, owing_count, overdue_zar, overdue_count, statement_zar, statement_count = (
            await self.db.execute(
                select(*bucket(balance > 0), *bucket(overdue), *bucket(statement)).where(
                    TaxInvoice.is_archive.is_(False)
                )
            )
        ).one()
        payments = await PaymentService(self.db).summary()
        return InvoiceSummary(
            outstanding_zar=cents(owing_zar),
            outstanding_count=owing_count,
            overdue_zar=cents(overdue_zar),
            overdue_count=overdue_count,
            on_statement_zar=cents(statement_zar),
            on_statement_count=statement_count,
            paid_this_month_zar=payments.received_this_month_zar,
            paid_this_month_count=payments.received_this_month_count,
        )

    async def set_archived(
        self, invoice_id: uuid.UUID, archived: bool, user_id: Optional[uuid.UUID] = None
    ) -> InvoiceResponse:
        """Hide an invoice from the active list. It stays in the books, VAT and reports."""
        async with unit_of_work(self.db):
            invoice = await self.crud.get_by_id(invoice_id, for_update=True)
            if invoice is None:
                raise NotFoundError("Invoice not found")
            assert_operational_document(invoice)
            if (invoice.archived_at is not None) == archived:
                raise ValidationError(
                    "This invoice is already archived"
                    if archived
                    else "This invoice is not archived"
                )
            invoice.archived_at = datetime.datetime.now(datetime.timezone.utc) if archived else None
            invoice.archived_by_id = user_id if archived else None
            await self.crud.commit_refresh(invoice)
        return await self.get(invoice_id, user_id)

    async def get(
        self,
        invoice_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> InvoiceResponse:
        invoice = await self.crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        return await self._to_response(invoice, viewer_user_id)

    async def _staff_name(self, staff_id: Optional[uuid.UUID]) -> str:
        staff = await self.db.get(SalesStaff, staff_id) if staff_id else None
        return staff.name if staff else "none"

    async def update(
        self, invoice_id: uuid.UUID, data: InvoiceUpdate, user_id: uuid.UUID
    ) -> InvoiceResponse:
        async with unit_of_work(self.db):
            invoice = await self.crud.get_by_id(invoice_id, for_update=True)
            if invoice is None:
                raise NotFoundError("Invoice not found")
            assert_operational_document(invoice)
            if "note_internal" in data.model_fields_set:
                invoice.note_internal = data.note_internal
            if "sales_staff_id" in data.model_fields_set:
                if data.sales_staff_id is not None:
                    await SalesStaffService(self.db).assert_assignable(data.sales_staff_id)
                if data.sales_staff_id != invoice.sales_staff_id:
                    before = await self._staff_name(invoice.sales_staff_id)
                    after = await self._staff_name(data.sales_staff_id)
                    await self.events.record(
                        BooksDocumentType.INVOICE,
                        invoice.id,
                        BooksEventAction.UPDATED,
                        actor_user_id=user_id,
                        note=f"Sales colleague: {before} → {after}",
                    )
                invoice.sales_staff_id = data.sales_staff_id
            await self.crud.commit_refresh(invoice)
        return await self.get(invoice_id, user_id)

    async def preview(self, data: InvoicePreviewRequest, user_id: uuid.UUID) -> SalePricePreview:
        """The cart's prices and totals exactly as creating the invoice would store them."""
        customer = await require_active_customer(self.db, data.customer_id)
        _, preview = await self._price_lines(customer, data.lines, user_id, enforce=False)
        return preview

    async def create_manual(self, data: ManualInvoiceCreate, user_id: uuid.UUID) -> InvoiceResponse:
        """A back-office invoice: a colleague as at the till, on account or already paid."""
        await SalesStaffService(self.db).check_sale_colleague(data.sales_staff_id)
        return await self.create(
            data, user_id, on_account=data.payment is None, payment=data.payment
        )

    async def create(
        self,
        data: InvoiceCreate,
        user_id: Optional[uuid.UUID] = None,
        *,
        on_account: bool = False,
        payment: Optional[InvoicePaymentCreate] = None,
    ) -> InvoiceResponse:
        await SkuArchiveService(self.db).lock_skus(
            [line.sku_id for line in data.lines if line.sku_id is not None]
        )
        customer = await require_active_customer(self.db, data.customer_id)

        line_models, priced = await self._price_lines(customer, data.lines, user_id, enforce=True)
        total_inc = priced.total_inc_vat
        if priced.subtotal_ex_vat <= 0:
            raise ValidationError("Invoice total must be positive")

        override_note = await self.credit.assert_allowed(
            customer,
            total_inc,
            credit_override=data.credit_override,
            credit_override_reason=data.credit_override_reason,
            user_id=user_id,
        )

        async with unit_of_work(self.db):
            invoice = await TaxInvoiceIssue(self.db).issue(
                customer=customer,
                issue_date=data.issue_date,
                due_date=data.due_date,
                lines=line_models,
                vat_rate=priced.vat_rate,
                prices_include_vat=shows_prices_including_vat(customer),
                memo="Tax invoice",
                actor_user_id=user_id,
                event_note=override_note,
                sales_staff_id=data.sales_staff_id,
                on_account=on_account,
                note_printed=data.note_printed,
                note_internal=data.note_internal,
            )
            if payment is not None:
                # Same transaction: a refused payment leaves no invoice behind.
                await PaymentService(self.db).stage_payment_in(
                    PaymentCreate(
                        direction="in",
                        invoice_id=invoice.id,
                        amount=total_inc,
                        currency="ZAR",
                        paid_on=payment.paid_on,
                        tender=payment.tender,
                        reference=payment.reference,
                    ),
                    user_id,
                )
            await self.crud.commit_refresh(invoice)

        reloaded = await self.crud.get_by_id(invoice.id)
        assert reloaded is not None
        return await self._to_response(reloaded, user_id)

    async def document_data(self, invoice_id: uuid.UUID) -> DocumentData:
        invoice = await self.crud.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found")
        assert_operational_document(invoice)

        lines = []
        for line in invoice.lines:
            description = line.description
            sku = await self.sku_crud.get_by_id(line.sku_id) if line.sku_id else None
            if sku is not None and sku.carton_count > 1:
                cartons = line.qty * sku.carton_count
                description = f"{description} - Ships in {cartons} cartons"
            printed_warning = customer_price_warning(line.price_warning)
            if printed_warning:
                description = f"{description} — {printed_warning}"
            lines.append(
                DocumentLine(
                    description=description,
                    qty=str(line.qty),
                    unit=format_pdf_unit(
                        line.unit_ex_vat, invoice.prices_include_vat, invoice.vat_rate
                    ),
                    ex_vat=f"{line.ex_vat:.2f}",
                    vat=f"{line.vat_amount:.2f}",
                    inc_vat=f"{line.inc_vat:.2f}",
                    discount=format_pdf_discount(line.discount_percent),
                    sku_ref=sku.our_ref if sku is not None else None,
                )
            )
        customer = invoice.customer
        balance = invoice.total_inc_vat - invoice.amount_paid
        status = None
        if invoice.total_inc_vat > 0 and balance <= 0:
            status = "paid"
        elif invoice.on_account:
            status = "on_statement"
        return DocumentData(
            kind="invoice",
            number=invoice.invoice_number,
            issue_date=invoice.issue_date.isoformat(),
            details=[("Due date", invoice.due_date.isoformat())] if invoice.due_date else [],
            served_by=await SalesStaffService(self.db).served_by(invoice.sales_staff_id),
            party=DocumentParty(
                label="Buyer",
                name=customer.name,
                address=customer.billing_address,
                vat_number=customer.vat_number,
            ),
            lines=lines,
            subtotal_ex_vat=f"{invoice.subtotal_ex_vat:.2f}",
            vat_amount=f"{invoice.vat_amount:.2f}",
            vat_rate=invoice.vat_rate,
            total=f"{invoice.total_inc_vat:.2f}",
            payments=[("Paid", f"{invoice.amount_paid:.2f}"), ("Balance owing", f"{balance:.2f}")],
            unit_basis_note=pdf_unit_basis_note(invoice.prices_include_vat),
            unit_header=pdf_unit_header(invoice.prices_include_vat),
            # Only the printed note; the internal note never reaches the document.
            note=invoice.note_printed,
            status=status,
            payment_reference=True,
        )

    async def serve_pdf(self, invoice_id: uuid.UUID) -> Response:
        data = await self.document_data(invoice_id)
        pdf_bytes = await SettingsService(self.db).render_document(data)
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def _price_lines(
        self,
        customer,
        lines: list[InvoiceLineCreate],
        user_id: Optional[uuid.UUID],
        *,
        enforce: bool,
    ) -> tuple[list[InvoiceLine], SalePricePreview]:
        """Price every line through Sale line pricing; a free-text line charges its own unit."""
        requests = []
        for line in lines:
            sku = None
            if line.sku_id is not None:
                sku = await self.sku_crud.get_by_id(line.sku_id)
                if sku is None:
                    raise NotFoundError("SKU not found")
                assert_sku_sellable(sku)
            requests.append(
                SaleLineRequest(
                    sku=sku,
                    qty=line.qty,
                    discount_percent=line.discount_percent,
                    unit_ex_vat=line.unit_ex_vat,
                )
            )
        pricing = await SaleLinePricing.for_customer(
            self.db,
            customer,
            await PricingAuthority.of(self.db, user_id),
            enforce_required_list=True,
        )
        preview = await pricing.price(requests, enforce=enforce)
        models = [
            InvoiceLine(
                description=line.description,
                qty=line.qty,
                unit_ex_vat=priced.unit_ex_vat,
                discount_percent=priced.discount_percent,
                ex_vat=priced.ex_vat,
                inc_vat=priced.inc_vat,
                vat_amount=priced.vat_amount,
                sort_order=index,
                sku_id=line.sku_id,
                price_warning=priced.price_warning,
            )
            for index, (line, priced) in enumerate(zip(lines, preview.lines, strict=True))
        ]
        return models, preview

    async def _staff_names(self) -> dict[uuid.UUID, str]:
        return dict((await self.db.execute(select(SalesStaff.id, SalesStaff.name))).tuples().all())

    @staticmethod
    def _to_list_item(
        invoice: TaxInvoice, staff_names: Optional[dict[uuid.UUID, str]] = None
    ) -> InvoiceListItem:
        balance = invoice.total_inc_vat - invoice.amount_paid
        return InvoiceListItem(
            is_archive=invoice.is_archive,
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            subtotal_ex_vat=invoice.subtotal_ex_vat,
            vat_amount=_response_money(invoice, invoice.vat_amount),
            total_inc_vat=_response_money(invoice, invoice.total_inc_vat),
            amount_paid=invoice.amount_paid,
            balance=_response_money(invoice, balance),
            payment_status="unknown" if invoice.is_archive else invoice.payment_status.value,
            **_lifecycle_fields(invoice),
            sales_staff_id=invoice.sales_staff_id,
            sales_staff_name=(staff_names or {}).get(invoice.sales_staff_id)
            if invoice.sales_staff_id
            else None,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )

    async def _to_response(
        self,
        invoice: TaxInvoice,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> InvoiceResponse:
        balance = invoice.total_inc_vat - invoice.amount_paid
        response = InvoiceResponse(
            is_archive=invoice.is_archive,
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            customer_id=invoice.customer_id,
            customer_name=invoice.customer.name,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            subtotal_ex_vat=invoice.subtotal_ex_vat,
            vat_amount=_response_money(invoice, invoice.vat_amount),
            total_inc_vat=_response_money(invoice, invoice.total_inc_vat),
            amount_paid=invoice.amount_paid,
            balance=_response_money(invoice, balance),
            payment_status="unknown" if invoice.is_archive else invoice.payment_status.value,
            **_lifecycle_fields(invoice),
            note_printed=invoice.note_printed,
            note_internal=invoice.note_internal,
            sales_staff_id=invoice.sales_staff_id,
            sales_staff_name=await self.db.scalar(
                select(SalesStaff.name).where(SalesStaff.id == invoice.sales_staff_id)
            )
            if invoice.sales_staff_id
            else None,
            prices_include_vat=invoice.prices_include_vat,
            vat_rate=invoice.vat_rate,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    unit_inc_vat=ex_to_inc(line.unit_ex_vat, invoice.vat_rate),
                    discount_percent=line.discount_percent,
                    ex_vat=line.ex_vat,
                    inc_vat=_response_money(invoice, line.inc_vat),
                    vat_amount=_response_money(invoice, line.vat_amount),
                    sort_order=line.sort_order,
                    sku_id=line.sku_id,
                    price_warning=line.price_warning,
                    till_no_stock_required=line.till_no_stock_required,
                    exclude_from_commission=line.exclude_from_commission,
                )
                for line in invoice.lines
            ],
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
        )
        await annotate_line_warnings(
            self.db,
            response.lines,
            viewer_user_id=viewer_user_id,
            inclusive_vat_rate=invoice.vat_rate if invoice.prices_include_vat else None,
        )
        return response


def _lifecycle_fields(invoice: TaxInvoice) -> dict[str, object]:
    """Source, settlement status and staff archiving, shared by the list and detail."""
    if invoice.is_archive:
        status = "unknown"
    elif invoice.payment_status == SettlementStatus.PAID:
        status = "paid"
    elif invoice.due_date is not None and invoice.due_date < datetime.date.today():
        status = "overdue"
    elif invoice.payment_status == SettlementStatus.PARTIALLY_PAID:
        status = "partially_paid"
    else:
        status = "on_statement" if invoice.on_account else "unpaid"
    return {
        "on_account": invoice.on_account,
        "source": "imported" if invoice.is_archive else invoice.source,
        "status": status,
        "is_archived": invoice.archived_at is not None,
        "archived_at": invoice.archived_at,
    }


def _response_money(invoice: TaxInvoice, value: Decimal) -> Decimal:
    # Live operations keep their established cent-valued API contract. Historical
    # source VAT and gross amounts retain all four stored decimal places.
    return value if invoice.is_archive else value.quantize(CENT)
