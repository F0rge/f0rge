from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.layby import LaybyCRUD
from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.models.journal import JournalDocumentType
from app.models.layby import Layby, LaybyLine, LaybyPayment, LaybyStatus
from app.models.location import LocationType
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.layby import (
    LaybyCreate,
    LaybyLineResponse,
    LaybyPaymentCreate,
    LaybyPaymentResponse,
    LaybyResponse,
)
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_COGS,
    CODE_DEPOSITS,
    CODE_INVENTORY,
    CODE_SALES,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.vat import CENT, ex_to_inc
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
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.posting = LedgerPostingService(db)

    async def list(self) -> list[LaybyResponse]:
        rows = await self.crud.list_all()
        return [self._to_response(row) for row in rows]

    async def get(self, layby_id: uuid.UUID) -> LaybyResponse:
        return self._to_response(await self._get_or_404(layby_id))

    async def create(self, data: LaybyCreate, user_id: uuid.UUID) -> LaybyResponse:
        customer = await self.customer_crud.get_by_id(data.customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")

        location = await self.location_crud.get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot create layby at archived location")

        if data.hold_stock:
            if location.type != LocationType.SHOWROOM:
                raise ConflictError("Layby stock hold is only allowed at showroom locations")
            await self.stocktakes.assert_location_unlocked(data.location_id)

        line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
            data.lines,
            data.location_id,
            data.hold_stock,
        )

        if data.deposit_amount > total_inc:
            raise ValidationError("Deposit cannot exceed layby total")

        layby_number = await self.crud.get_next_layby_number()
        paid_on = datetime.date.today()
        layby = Layby(
            layby_number=layby_number,
            customer_id=data.customer_id,
            location_id=data.location_id,
            due_date=data.due_date,
            hold_stock=data.hold_stock,
            status=LaybyStatus.OPEN,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
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
            await self.crud.add_and_flush(layby)
            payment.layby_id = layby.id
            await self.crud.add_and_flush(payment)

            await self._post_deposit(payment, layby.layby_number, data.tender)

            if data.hold_stock:
                for line in line_models:
                    await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=data.location_id,
                        qty=line.qty,
                        user_id=user_id,
                        source=UnitCostAuditSource.LAYBY,
                        note=f"Layby {layby_number} hold",
                    )

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
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)

        for index, line in enumerate(layby.lines):
            ex_vat = (Decimal(line.qty) * line.unit_ex_vat).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
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

        invoice_number = await self.invoice_crud.get_next_invoice_number()
        invoice = TaxInvoice(
            invoice_number=invoice_number,
            customer_id=layby.customer_id,
            issue_date=issue_date,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_total,
            total_inc_vat=total_inc,
            amount_paid=total_inc,
            lines=invoice_line_models,
        )

        async with unit_of_work(self.db):
            await self.invoice_crud.add_and_flush(invoice)

            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Layby tax invoice {invoice_number}",
                [
                    (CODE_AR, total_inc, Decimal(0)),
                    (CODE_SALES, Decimal(0), subtotal),
                    (CODE_VAT, Decimal(0), vat_total),
                ],
            )

            await self.posting.post(
                JournalDocumentType.PAYMENT,
                layby.id,
                f"Apply layby deposits {layby.layby_number}",
                [
                    (CODE_DEPOSITS, total_inc, Decimal(0)),
                    (CODE_AR, Decimal(0), total_inc),
                ],
            )

            total_cogs = Decimal(0)
            for line in layby.lines:
                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    line.sku_id,
                    layby.location_id,
                )
                if loc_stock is None or loc_stock.unit_cost_zar is None:
                    raise ValidationError("unit cost required")
                total_cogs += (loc_stock.unit_cost_zar * line.qty).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )

            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for layby {layby.layby_number}",
                    [
                        (CODE_COGS, total_cogs, Decimal(0)),
                        (CODE_INVENTORY, Decimal(0), total_cogs),
                    ],
                )

            if not layby.hold_stock:
                for line in layby.lines:
                    await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=layby.location_id,
                        qty=line.qty,
                        user_id=user_id,
                        source=UnitCostAuditSource.LAYBY,
                        note=f"Layby {layby.layby_number} complete",
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
                    loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                        line.sku_id,
                        layby.location_id,
                    )
                    if loc_stock is None or loc_stock.unit_cost_zar is None:
                        raise ValidationError("unit cost required")
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=line.sku_id,
                        location_id=layby.location_id,
                        qty=line.qty,
                        unit_cost_zar=loc_stock.unit_cost_zar,
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

    async def _build_line_models(
        self,
        lines: list,
        location_id: uuid.UUID,
        hold_stock: bool,
    ) -> tuple[list[LaybyLine], Decimal, Decimal, Decimal]:
        qty_by_sku: dict[uuid.UUID, int] = {}
        models: list[LaybyLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)

        for line in lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            if sku.retail_ex_vat is None or sku.retail_ex_vat <= 0:
                raise ValidationError(f"SKU {sku.our_ref} has no retail price")

            qty_by_sku[line.sku_id] = qty_by_sku.get(line.sku_id, 0) + line.qty

            unit_ex = sku.retail_ex_vat
            ex_vat = (Decimal(line.qty) * unit_ex).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            models.append(
                LaybyLine(
                    sku_id=line.sku_id,
                    qty=line.qty,
                    unit_ex_vat=unit_ex,
                )
            )

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

        return models, subtotal, vat_total, total_inc

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

    def _to_response(self, layby: Layby) -> LaybyResponse:
        balance = layby.total_inc_vat - layby.amount_paid
        return LaybyResponse(
            id=layby.id,
            layby_number=layby.layby_number,
            customer_id=layby.customer_id,
            customer_name=layby.customer.name,
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
