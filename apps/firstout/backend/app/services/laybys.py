from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.services.party_archive import require_active_customer
from app.services.sellability import assert_sku_sellable
from app.services.sku_archive import SkuArchiveService
from app.crud.layby import LaybyCRUD
from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.models.journal import JournalDocumentType
from app.models.layby import Layby, LaybyLine, LaybyPayment, LaybyStatus
from app.models.location import LocationType
from app.models.tax_invoice import InvoiceLine
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.layby import (
    LaybyCreate,
    LaybyPreviewRequest,
    LaybyLineResponse,
    LaybyListItem,
    LaybyPaymentCreate,
    LaybyPaymentResponse,
    LaybyResponse,
)
from app.schemas.page import Page, PageParams
from app.schemas.sale_line_pricing import SalePricePreview
from app.services.layby_pdf import build_layby_pdf
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_BANK,
    CODE_DEPOSITS,
    CODE_INVENTORY,
    LedgerPostingService,
)
from app.services.settings import SettingsService
from app.services.stock_movements import StockCost, StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.pricing import shows_prices_including_vat
from app.services.tax_invoice_issue import Deposits, TaxInvoiceIssue
from app.services.sale_line_pricing import (
    PricingAuthority,
    SaleLinePricing,
    SaleLineRequest,
    line_amounts,
)
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class LaybysService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LaybyCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)

    async def list(
        self,
        params: PageParams,
        status: Optional[LaybyStatus] = None,
    ) -> Page[LaybyListItem]:
        rows, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            status=status,
        )
        return Page(
            items=[self._to_list_item(row) for row in rows],
            total=total,
        )

    async def get(self, layby_id: uuid.UUID) -> LaybyResponse:
        return self._to_response(await self._get_or_404(layby_id))

    async def build_pdf_bytes(self, layby_id: uuid.UUID) -> tuple[bytes, str, Layby]:
        layby = await self._get_or_404(layby_id)
        seller = await SettingsService(self.db).build_seller_details()
        balance = layby.total_inc_vat - layby.amount_paid
        pdf_bytes = build_layby_pdf(
            layby_number=layby.layby_number,
            customer_name=layby.customer.name,
            due_date=layby.due_date.isoformat(),
            lines=[(line.sku.name, line.qty) for line in layby.lines],
            amount_paid=f"{layby.amount_paid:.2f}",
            balance=f"{balance:.2f}",
            total_inc_vat=f"{layby.total_inc_vat:.2f}",
            seller=seller,
            status=layby.status.value,
        )
        return pdf_bytes, f"{layby.layby_number}.pdf", layby

    async def serve_pdf(self, layby_id: uuid.UUID) -> Response:
        pdf_bytes, _, _ = await self.build_pdf_bytes(layby_id)
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def preview(self, data: LaybyPreviewRequest, user_id: uuid.UUID) -> SalePricePreview:
        """The layby's prices and totals exactly as creating it would store them."""
        customer = await require_active_customer(self.db, data.customer_id)
        return await self._price(customer, data.lines, user_id, enforce=False)

    async def create(self, data: LaybyCreate, user_id: uuid.UUID) -> LaybyResponse:
        customer = await require_active_customer(self.db, data.customer_id)

        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot create layby at archived location")

        if data.hold_stock:
            if location.type != LocationType.SHOWROOM:
                raise ConflictError("Layby stock hold is only allowed at showroom locations")
            await self.stocktakes.assert_location_unlocked(data.location_id)

        line_models, priced = await self._build_line_models(
            customer,
            data.lines,
            data.location_id,
            data.hold_stock,
            user_id,
        )

        if data.deposit_amount > priced.total_inc_vat:
            raise ValidationError("Deposit cannot exceed layby total")

        paid_on = datetime.date.today()
        layby = Layby(
            layby_number="",
            customer_id=data.customer_id,
            location_id=data.location_id,
            due_date=data.due_date,
            hold_stock=data.hold_stock,
            status=LaybyStatus.OPEN,
            subtotal_ex_vat=priced.subtotal_ex_vat,
            vat_amount=priced.vat_amount,
            total_inc_vat=priced.total_inc_vat,
            vat_rate=priced.vat_rate,
            amount_paid=Decimal(0),
            notes=data.notes,
            created_by_user_id=user_id,
            lines=line_models,
        )
        payment = LaybyPayment(
            amount=data.deposit_amount,
            tender=data.tender,
            paid_on=paid_on,
        )

        async with unit_of_work(self.db):
            layby.layby_number = await self.crud.get_next_layby_number()
            await self.crud.add_and_flush(layby)
            payment.layby_id = layby.id
            await self.crud.add_and_flush(payment)

            await self._post_deposit(payment, layby.layby_number, data.tender)

            if data.hold_stock:
                for line in line_models:
                    held = await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=data.location_id,
                        qty=line.qty,
                        user_id=user_id,
                        source=UnitCostAuditSource.LAYBY,
                        note=f"Layby {layby.layby_number} hold",
                    )
                    line.hold_unit_cost_zar = held.unit_cost_zar

            layby.amount_paid = data.deposit_amount
            self._refresh_status(layby)

        return self._to_response(await self._get_or_404(layby.id))

    async def add_payment(
        self,
        layby_id: uuid.UUID,
        data: LaybyPaymentCreate,
        user_id: uuid.UUID,
    ) -> LaybyResponse:
        layby = await self._require_active(layby_id)
        new_total_paid = layby.amount_paid + data.amount
        if new_total_paid > layby.total_inc_vat:
            raise ValidationError("Payment would exceed layby total")

        paid_on = datetime.date.today()
        payment = LaybyPayment(
            layby_id=layby.id,
            amount=data.amount,
            tender=data.tender,
            paid_on=paid_on,
        )

        async with unit_of_work(self.db):
            await self.crud.add_and_flush(payment)
            await self._post_deposit(payment, layby.layby_number, data.tender)
            layby.amount_paid = new_total_paid
            self._refresh_status(layby)

        return self._to_response(await self._get_or_404(layby.id))

    async def complete(self, layby_id: uuid.UUID, user_id: uuid.UUID) -> LaybyResponse:
        layby = await self._require_ready(layby_id)

        if not layby.hold_stock:
            await self.stocktakes.assert_location_unlocked(layby.location_id)

        issue_date = datetime.date.today()

        invoice_line_models: list[InvoiceLine] = []
        total_inc = Decimal(0)

        for index, line in enumerate(layby.lines):
            # Layby lines carry no discount. The rate is the layby's, fixed when it was
            # concluded (ADR 0003, SARS 2018 FAQ Q13), not today's setting.
            ex_vat, line_vat, inc_vat = line_amounts(
                line.unit_ex_vat, line.qty, None, layby.vat_rate
            )
            total_inc += inc_vat
            invoice_line_models.append(
                InvoiceLine(
                    description=line.sku.name,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=line.sku_id,
                )
            )

        async with unit_of_work(self.db):
            # A ready layby is fully paid: its deposits settle the whole invoice.
            invoice = await TaxInvoiceIssue(self.db).issue(
                customer=layby.customer,
                issue_date=issue_date,
                lines=invoice_line_models,
                vat_rate=layby.vat_rate,
                prices_include_vat=shows_prices_including_vat(layby.customer),
                memo="Layby tax invoice",
                actor_user_id=user_id,
                deposits=Deposits(
                    source_id=layby.id,
                    memo=f"Apply layby deposits {layby.layby_number}",
                    amount=total_inc,
                ),
            )

            total_cogs = Decimal(0)
            cogs_parts: list[tuple[str, Decimal, Decimal]] = []
            for line, invoice_line in zip(layby.lines, invoice_line_models, strict=True):
                if layby.hold_stock:
                    sold = await self._held_cost(layby, line)
                else:
                    sold = await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=layby.location_id,
                        qty=line.qty,
                        user_id=user_id,
                        source=UnitCostAuditSource.LAYBY,
                        note=f"Layby {layby.layby_number} complete",
                    )
                line_cogs = sold.total_zar
                invoice_line.unit_cost_zar = sold.unit_cost_zar
                total_cogs += line_cogs
                cogs_code = await self.category_posting.cogs_code_for_sku(line.sku)
                cogs_parts.append((cogs_code, line_cogs, Decimal(0)))

            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for layby {layby.layby_number}",
                    self.category_posting.collapse(
                        [
                            *cogs_parts,
                            (CODE_INVENTORY, Decimal(0), total_cogs),
                        ]
                    ),
                    entry_date=issue_date,
                )

            layby.invoice_id = invoice.id
            layby.status = LaybyStatus.COMPLETED

        return self._to_response(await self._get_or_404(layby.id))

    async def cancel(self, layby_id: uuid.UUID, user_id: uuid.UUID) -> LaybyResponse:
        layby = await self._require_cancellable(layby_id)

        if layby.hold_stock:
            await self.stocktakes.assert_location_unlocked(layby.location_id)

        async with unit_of_work(self.db):
            if layby.hold_stock:
                for line in layby.lines:
                    held = await self._held_cost(layby, line)
                    if held.unit_cost_zar is None:
                        raise ValidationError("unit cost required")
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=line.sku_id,
                        location_id=layby.location_id,
                        qty=line.qty,
                        unit_cost_zar=held.unit_cost_zar,
                        user_id=user_id,
                        source=UnitCostAuditSource.LAYBY,
                        note=f"Layby {layby.layby_number} cancel restock",
                    )

            if layby.amount_paid > 0:
                refund_doc_id = layby.payments[-1].id if layby.payments else layby.id
                await self.posting.post(
                    JournalDocumentType.PAYMENT,
                    refund_doc_id,
                    f"Refund layby deposits {layby.layby_number}",
                    [
                        (CODE_DEPOSITS, layby.amount_paid, Decimal(0)),
                        (CODE_BANK, Decimal(0), layby.amount_paid),
                    ],
                )

            layby.status = LaybyStatus.CANCELLED

        return self._to_response(await self._get_or_404(layby.id))

    async def _held_cost(self, layby: Layby, line: LaybyLine) -> StockCost:
        """The cost the held stock left the shelf at.

        Holds without one (laybys held before this release, or held while the location's
        cost was unknown) keep the old rule: the location's current average.
        """
        unit_cost = line.hold_unit_cost_zar
        if unit_cost is None:
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id, layby.location_id
            )
            unit_cost = loc_stock.unit_cost_zar if loc_stock is not None else None
        return StockCost(Decimal(line.qty), unit_cost)

    async def _price(
        self, customer, lines: list, user_id: uuid.UUID, *, enforce: bool = True
    ) -> SalePricePreview:
        requests = []
        for line in lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            assert_sku_sellable(sku)
            # Layby lines carry no discount or price override.
            requests.append(SaleLineRequest(sku=sku, qty=line.qty))
        pricing = await SaleLinePricing.for_customer(
            self.db, customer, await PricingAuthority.of(self.db, user_id)
        )
        return await pricing.price(requests, enforce=enforce)

    async def _build_line_models(
        self,
        customer,
        lines: list,
        location_id: uuid.UUID,
        hold_stock: bool,
        user_id: uuid.UUID,
    ) -> tuple[list[LaybyLine], SalePricePreview]:
        await SkuArchiveService(self.db).lock_skus([line.sku_id for line in lines])
        priced = await self._price(customer, lines, user_id)
        models = [
            LaybyLine(sku_id=line.sku_id, qty=line.qty, unit_ex_vat=price.unit_ex_vat)
            for line, price in zip(lines, priced.lines, strict=True)
        ]
        qty_by_sku: dict[uuid.UUID, int] = {}
        for line in lines:
            qty_by_sku[line.sku_id] = qty_by_sku.get(line.sku_id, 0) + line.qty

        if hold_stock:
            for sku_id, qty in qty_by_sku.items():
                sku = await self.sku_crud.get_by_id(sku_id)
                assert sku is not None
                location_stock = await self.location_stock_crud.get_by_sku_and_location(
                    sku_id,
                    location_id,
                )
                if location_stock is None or location_stock.on_hand < qty:
                    raise ConflictError(
                        f"Insufficient on-hand quantity for {sku.our_ref} at this location"
                    )

        return models, priced

    async def _post_deposit(
        self,
        payment: LaybyPayment,
        layby_number: str,
        tender: str,
    ) -> None:
        await self.posting.post(
            JournalDocumentType.PAYMENT,
            payment.id,
            f"Layby deposit {layby_number} ({tender})",
            [
                (CODE_BANK, payment.amount, Decimal(0)),
                (CODE_DEPOSITS, Decimal(0), payment.amount),
            ],
            entry_date=payment.paid_on,
        )

    async def _get_or_404(self, layby_id: uuid.UUID) -> Layby:
        layby = await self.crud.get_by_id(layby_id)
        if layby is None:
            raise NotFoundError("Layby not found")
        return layby

    async def _require_active(self, layby_id: uuid.UUID) -> Layby:
        layby = await self._get_or_404(layby_id)
        if layby.status not in (LaybyStatus.OPEN, LaybyStatus.READY):
            raise ConflictError("Layby is not active")
        return layby

    async def _require_ready(self, layby_id: uuid.UUID) -> Layby:
        layby = await self._get_or_404(layby_id)
        if layby.status != LaybyStatus.READY:
            raise ConflictError("Layby is not ready to complete")
        return layby

    async def _require_cancellable(self, layby_id: uuid.UUID) -> Layby:
        layby = await self._get_or_404(layby_id)
        if layby.status not in (LaybyStatus.OPEN, LaybyStatus.READY):
            raise ConflictError("Layby cannot be cancelled")
        return layby

    @staticmethod
    def _refresh_status(layby: Layby) -> None:
        if layby.amount_paid >= layby.total_inc_vat:
            layby.status = LaybyStatus.READY
        else:
            layby.status = LaybyStatus.OPEN

    @staticmethod
    def _items_label(layby: Layby) -> str:
        if not layby.lines:
            return "—"
        first = layby.lines[0]
        base = f"{first.sku.our_ref} — {first.sku.name}"
        if len(layby.lines) == 1:
            return base
        return f"{base} +{len(layby.lines) - 1}"

    def _to_list_item(self, layby: Layby) -> LaybyListItem:
        balance = layby.total_inc_vat - layby.amount_paid
        return LaybyListItem(
            id=layby.id,
            layby_number=layby.layby_number,
            customer_id=layby.customer_id,
            customer_name=layby.customer.name,
            customer_email=layby.customer.email,
            location_id=layby.location_id,
            location_name=layby.location.name,
            invoice_id=layby.invoice_id,
            due_date=layby.due_date,
            hold_stock=layby.hold_stock,
            status=layby.status,
            subtotal_ex_vat=layby.subtotal_ex_vat,
            vat_amount=layby.vat_amount,
            total_inc_vat=layby.total_inc_vat,
            amount_paid=layby.amount_paid,
            balance=balance,
            notes=layby.notes,
            items_label=self._items_label(layby),
            created_at=layby.created_at,
            updated_at=layby.updated_at,
        )

    def _to_response(self, layby: Layby) -> LaybyResponse:
        balance = layby.total_inc_vat - layby.amount_paid
        return LaybyResponse(
            id=layby.id,
            layby_number=layby.layby_number,
            customer_id=layby.customer_id,
            customer_name=layby.customer.name,
            customer_email=layby.customer.email,
            location_id=layby.location_id,
            location_name=layby.location.name,
            invoice_id=layby.invoice_id,
            due_date=layby.due_date,
            hold_stock=layby.hold_stock,
            status=layby.status,
            subtotal_ex_vat=layby.subtotal_ex_vat,
            vat_amount=layby.vat_amount,
            total_inc_vat=layby.total_inc_vat,
            vat_rate=layby.vat_rate,
            amount_paid=layby.amount_paid,
            balance=balance,
            notes=layby.notes,
            lines=[
                LaybyLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    our_ref=line.sku.our_ref,
                    name=line.sku.name,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                )
                for line in layby.lines
            ],
            payments=[
                LaybyPaymentResponse(
                    id=payment.id,
                    amount=payment.amount,
                    tender=payment.tender,
                    paid_on=payment.paid_on,
                )
                for payment in layby.payments
            ],
            created_at=layby.created_at,
            updated_at=layby.updated_at,
        )
