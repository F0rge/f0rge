from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sales_order import SalesOrderCRUD
from app.crud.sku import SkuCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.quote import Quote, QuoteStatus
from app.models.sales_order import (
    SalesOrder,
    SalesOrderLine,
    SalesOrderPayment,
    SalesOrderStatus,
)
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.page import Page, PageParams
from app.schemas.quote import QuoteAccept
from app.schemas.sales_order import (
    SalesOrderConfirm,
    SalesOrderCreate,
    SalesOrderLineResponse,
    SalesOrderListItem,
    SalesOrderPaymentCreate,
    SalesOrderPaymentResponse,
    SalesOrderResponse,
)
from app.services.books_periods import assert_date_postable
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_DEPOSITS,
    CODE_INVENTORY,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.payment_terms import compute_due_date
from app.services.pricing import resolve_unit_ex_vat
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class SalesOrdersService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SalesOrderCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)

    async def list(
        self,
        params: PageParams,
        status: Optional[SalesOrderStatus] = None,
        customer_id: Optional[uuid.UUID] = None,
    ) -> Page[SalesOrderListItem]:
        rows, total = await self.crud.list_page(
            limit=params.limit,
            offset=params.offset,
            q=params.q,
            status=status,
            customer_id=customer_id,
        )
        return Page(items=[self._to_list_item(row) for row in rows], total=total)

    async def get(self, sales_order_id: uuid.UUID) -> SalesOrderResponse:
        return self._to_response(await self._get_or_404(sales_order_id))

    async def create_draft(
        self,
        data: SalesOrderCreate,
        *,
        user_id: Optional[uuid.UUID] = None,
    ) -> SalesOrderResponse:
        customer = await self._require_customer(data.customer_id)
        line_models, subtotal, vat_amount, total_inc = await self._build_line_models(
            customer,
            data.lines,
        )
        order = SalesOrder(
            so_number="",
            customer_id=customer.id,
            hold_stock=False,
            awaiting_stock=False,
            status=SalesOrderStatus.DRAFT,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            amount_paid=Decimal(0),
            notes=data.notes,
            created_by_user_id=user_id,
            lines=line_models,
        )
        async with unit_of_work(self.db):
            order.so_number = await self.crud.get_next_so_number()
            await self.crud.add_and_flush(order)
        return self._to_response(await self._get_or_404(order.id))

    async def create_from_quote(
        self,
        quote: Quote,
        data: QuoteAccept,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        existing = await self.crud.get_by_quote_id(quote.id)
        if existing is not None:
            raise ConflictError("Quote already has a sales order")
        line_models = [
            SalesOrderLine(
                sku_id=line.sku_id,
                qty=line.qty,
                unit_ex_vat=line.unit_ex_vat,
                description=line.description,
                notes=line.notes,
                held_qty=0,
            )
            for line in quote.lines
        ]
        order = SalesOrder(
            so_number="",
            customer_id=quote.customer_id,
            quote_id=quote.id,
            location_id=data.location_id,
            hold_stock=False,
            awaiting_stock=False,
            status=SalesOrderStatus.OPEN,
            subtotal_ex_vat=quote.subtotal_ex_vat,
            vat_amount=quote.vat_amount,
            total_inc_vat=quote.total_inc_vat,
            amount_paid=Decimal(0),
            notes=quote.notes,
            created_by_user_id=user_id,
            lines=line_models,
        )
        async with unit_of_work(self.db):
            order.so_number = await self.crud.get_next_so_number()
            await self.crud.add_and_flush(order)
            quote.status = QuoteStatus.ACCEPTED
            if data.hold_stock:
                await self._apply_hold(order, data.location_id, user_id)
            if data.deposit is not None:
                await self._add_deposit_locked(
                    order,
                    SalesOrderPaymentCreate(amount=data.deposit.amount, tender=data.deposit.tender),
                )
        return self._to_response(await self._get_or_404(order.id))

    async def confirm(
        self,
        sales_order_id: uuid.UUID,
        data: SalesOrderConfirm,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        order = await self._get_or_404(sales_order_id)
        if order.status != SalesOrderStatus.DRAFT:
            raise ConflictError("Sales order is not a draft")
        async with unit_of_work(self.db):
            order.status = SalesOrderStatus.OPEN
            order.created_by_user_id = user_id
            order.location_id = data.location_id
            if data.hold_stock:
                await self._apply_hold(order, data.location_id, user_id)
            if data.deposit is not None:
                await self._add_deposit_locked(order, data.deposit)
        return self._to_response(await self._get_or_404(order.id))

    async def add_payment(
        self,
        sales_order_id: uuid.UUID,
        data: SalesOrderPaymentCreate,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        del user_id
        order = await self._require_open(sales_order_id)
        new_total = order.amount_paid + data.amount
        if new_total > order.total_inc_vat:
            raise ValidationError("Payment would exceed sales order total")
        async with unit_of_work(self.db):
            await self._add_deposit_locked(order, data)
        return self._to_response(await self._get_or_404(order.id))

    async def cancel(self, sales_order_id: uuid.UUID, user_id: uuid.UUID) -> SalesOrderResponse:
        order = await self._get_or_404(sales_order_id)
        if order.status not in (
            SalesOrderStatus.DRAFT,
            SalesOrderStatus.OPEN,
            SalesOrderStatus.AWAITING_STOCK,
        ):
            raise ConflictError("Sales order cannot be cancelled")
        location_ids = {
            line.hold_location_id for line in order.lines if line.hold_location_id is not None
        }
        for location_id in location_ids:
            await self.stocktakes.assert_location_unlocked(location_id)
        async with unit_of_work(self.db):
            for line in order.lines:
                if line.held_qty <= 0 or line.hold_location_id is None:
                    continue
                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    line.sku_id,
                    line.hold_location_id,
                )
                unit_cost = line.hold_unit_cost_zar
                if unit_cost is None:
                    if loc_stock is None or loc_stock.unit_cost_zar is None:
                        raise ValidationError("unit cost required")
                    unit_cost = loc_stock.unit_cost_zar
                await self.stock_movements.apply_incoming_qty(
                    sku_id=line.sku_id,
                    location_id=line.hold_location_id,
                    qty=line.held_qty,
                    unit_cost_zar=unit_cost,
                    user_id=user_id,
                    source=UnitCostAuditSource.SALES_ORDER,
                    note=f"Sales order {order.so_number} cancel restock",
                )
                line.held_qty = 0
            if order.amount_paid > 0:
                refund_doc_id = order.payments[-1].id if order.payments else order.id
                await self.posting.post(
                    JournalDocumentType.PAYMENT,
                    refund_doc_id,
                    f"Refund sales order deposits {order.so_number}",
                    [
                        (CODE_DEPOSITS, order.amount_paid, Decimal(0)),
                        (CODE_BANK, Decimal(0), order.amount_paid),
                    ],
                )
            order.status = SalesOrderStatus.CANCELLED
            order.hold_stock = False
        return self._to_response(await self._get_or_404(order.id))

    async def create_remainder_invoice(
        self,
        sales_order_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        order = await self._require_open(sales_order_id)
        if order.invoice_id is not None:
            raise ConflictError("Sales order already invoiced")
        issue_date = datetime.date.today()
        await assert_date_postable(self.db, issue_date)

        invoice_line_models: list[InvoiceLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        sales_parts: list[tuple[str, Decimal, Decimal]] = []
        for index, line in enumerate(order.lines):
            ex_vat = (Decimal(line.qty) * line.unit_ex_vat).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            sales_code = await self.category_posting.sales_code_for_sku(line.sku)
            sales_parts.append((sales_code, Decimal(0), ex_vat))
            invoice_line_models.append(
                InvoiceLine(
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=line.sku_id,
                )
            )

        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        team_settings = await TeamSettingsCRUD(self.db).get_or_create_for_team(team.id)
        due_date = compute_due_date(issue_date, order.customer, team_settings)
        deposit_total = order.amount_paid

        outgoing_needed = [line for line in order.lines if line.held_qty < line.qty]
        if outgoing_needed:
            location_id = order.location_id
            if location_id is None:
                raise ValidationError("Location is required to issue remaining stock")
            await self.stocktakes.assert_location_unlocked(location_id)

        async with unit_of_work(self.db):
            invoice_number = await self.invoice_crud.get_next_invoice_number()
            invoice = TaxInvoice(
                invoice_number=invoice_number,
                customer_id=order.customer_id,
                issue_date=issue_date,
                due_date=due_date,
                subtotal_ex_vat=subtotal,
                vat_amount=vat_total,
                total_inc_vat=total_inc,
                amount_paid=deposit_total,
                lines=invoice_line_models,
            )
            await self.invoice_crud.add_and_flush(invoice)
            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Sales order tax invoice {invoice_number}",
                self.category_posting.collapse(
                    [
                        (CODE_AR, total_inc, Decimal(0)),
                        *sales_parts,
                        (CODE_VAT, Decimal(0), vat_total),
                    ]
                ),
                entry_date=issue_date,
            )
            if deposit_total > 0:
                await self.posting.post(
                    JournalDocumentType.PAYMENT,
                    order.id,
                    f"Apply sales order deposits {order.so_number}",
                    [
                        (CODE_DEPOSITS, deposit_total, Decimal(0)),
                        (CODE_AR, Decimal(0), deposit_total),
                    ],
                    entry_date=issue_date,
                )

            total_cogs = Decimal(0)
            cogs_parts: list[tuple[str, Decimal, Decimal]] = []
            for line in order.lines:
                remaining = line.qty - line.held_qty
                if remaining > 0:
                    assert order.location_id is not None
                    await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=order.location_id,
                        qty=remaining,
                        user_id=user_id,
                        source=UnitCostAuditSource.SALES_ORDER,
                        note=f"Sales order {order.so_number} remainder",
                    )
                    line.held_qty = line.qty
                    line.hold_location_id = order.location_id
                loc_id = line.hold_location_id or order.location_id
                unit_cost = line.hold_unit_cost_zar
                if unit_cost is None and loc_id is not None:
                    loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                        line.sku_id,
                        loc_id,
                    )
                    if loc_stock is not None:
                        unit_cost = loc_stock.unit_cost_zar
                if unit_cost is None:
                    raise ValidationError("unit cost required")
                line_cogs = (unit_cost * line.qty).quantize(CENT, rounding=ROUND_HALF_UP)
                total_cogs += line_cogs
                cogs_code = await self.category_posting.cogs_code_for_sku(line.sku)
                cogs_parts.append((cogs_code, line_cogs, Decimal(0)))

            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for sales order {order.so_number}",
                    self.category_posting.collapse(
                        [
                            *cogs_parts,
                            (CODE_INVENTORY, Decimal(0), total_cogs),
                        ]
                    ),
                    entry_date=issue_date,
                )

            order.invoice_id = invoice.id
            order.status = SalesOrderStatus.INVOICED

        return self._to_response(await self._get_or_404(order.id))

    async def _apply_hold(
        self,
        order: SalesOrder,
        location_id: Optional[uuid.UUID],
        user_id: uuid.UUID,
    ) -> None:
        if location_id is None:
            raise ValidationError("location_id is required to hold stock")
        location = await self.location_crud.get_by_id(location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot hold stock at archived location")
        if location.type not in (LocationType.WAREHOUSE, LocationType.SHOWROOM):
            raise ConflictError(
                "Sales order hold is only allowed at warehouse or showroom locations"
            )
        await self.stocktakes.assert_location_unlocked(location_id)
        order.location_id = location_id
        any_unheld = False
        any_held = False
        for line in order.lines:
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id,
                location_id,
            )
            on_hand = loc_stock.on_hand if loc_stock is not None else 0
            if loc_stock is None or loc_stock.unit_cost_zar is None or on_hand < line.qty:
                any_unheld = True
                continue
            await self.stock_movements.apply_outgoing_qty(
                sku_id=line.sku_id,
                location_id=location_id,
                qty=line.qty,
                user_id=user_id,
                source=UnitCostAuditSource.SALES_ORDER,
                note=f"Sales order {order.so_number} hold",
            )
            line.held_qty = line.qty
            line.hold_location_id = location_id
            line.hold_unit_cost_zar = loc_stock.unit_cost_zar
            any_held = True
        order.hold_stock = any_held
        order.awaiting_stock = any_unheld
        if any_unheld and not any_held:
            order.status = SalesOrderStatus.AWAITING_STOCK
        else:
            order.status = SalesOrderStatus.OPEN

    async def _add_deposit_locked(
        self,
        order: SalesOrder,
        data: SalesOrderPaymentCreate,
    ) -> None:
        if data.amount > (order.total_inc_vat - order.amount_paid):
            raise ValidationError("Deposit cannot exceed remaining balance")
        paid_on = datetime.date.today()
        payment = SalesOrderPayment(
            sales_order_id=order.id,
            amount=data.amount,
            tender=data.tender,
            paid_on=paid_on,
        )
        await self.crud.add_and_flush(payment)
        await self.posting.post(
            JournalDocumentType.PAYMENT,
            payment.id,
            f"Sales order deposit {order.so_number} ({data.tender})",
            [
                (CODE_BANK, payment.amount, Decimal(0)),
                (CODE_DEPOSITS, Decimal(0), payment.amount),
            ],
            entry_date=paid_on,
        )
        order.amount_paid = order.amount_paid + data.amount

    async def _build_line_models(
        self,
        customer,
        lines,
    ) -> tuple[list[SalesOrderLine], Decimal, Decimal, Decimal]:
        models: list[SalesOrderLine] = []
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
                SalesOrderLine(
                    sku_id=sku.id,
                    qty=line.qty,
                    unit_ex_vat=unit_ex,
                    description=sku.name,
                    notes=getattr(line, "notes", None),
                    held_qty=0,
                )
            )
        return models, subtotal, vat_total, total_inc

    async def _require_customer(self, customer_id: uuid.UUID):
        customer = await self.customer_crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer

    async def _get_or_404(self, sales_order_id: uuid.UUID) -> SalesOrder:
        order = await self.crud.get_by_id(sales_order_id)
        if order is None:
            raise NotFoundError("Sales order not found")
        return order

    async def _require_open(self, sales_order_id: uuid.UUID) -> SalesOrder:
        order = await self._get_or_404(sales_order_id)
        if order.status not in (SalesOrderStatus.OPEN, SalesOrderStatus.AWAITING_STOCK):
            raise ConflictError("Sales order is not open")
        return order

    @staticmethod
    def _items_label(order: SalesOrder) -> str:
        if not order.lines:
            return "—"
        first = order.lines[0]
        base = f"{first.sku.our_ref} — {first.description}"
        if len(order.lines) == 1:
            return base
        return f"{base} +{len(order.lines) - 1}"

    def _to_list_item(self, order: SalesOrder) -> SalesOrderListItem:
        balance = order.total_inc_vat - order.amount_paid
        return SalesOrderListItem(
            id=order.id,
            so_number=order.so_number,
            customer_id=order.customer_id,
            customer_name=order.customer.name,
            quote_id=order.quote_id,
            location_id=order.location_id,
            location_name=order.location.name if order.location is not None else None,
            invoice_id=order.invoice_id,
            hold_stock=order.hold_stock,
            awaiting_stock=order.awaiting_stock,
            status=order.status,
            subtotal_ex_vat=order.subtotal_ex_vat,
            vat_amount=order.vat_amount,
            total_inc_vat=order.total_inc_vat,
            amount_paid=order.amount_paid,
            balance=balance,
            notes=order.notes,
            items_label=self._items_label(order),
            created_at=order.created_at,
            updated_at=order.updated_at,
        )

    def _to_response(self, order: SalesOrder) -> SalesOrderResponse:
        balance = order.total_inc_vat - order.amount_paid
        return SalesOrderResponse(
            id=order.id,
            so_number=order.so_number,
            customer_id=order.customer_id,
            customer_name=order.customer.name,
            quote_id=order.quote_id,
            location_id=order.location_id,
            location_name=order.location.name if order.location is not None else None,
            invoice_id=order.invoice_id,
            hold_stock=order.hold_stock,
            awaiting_stock=order.awaiting_stock,
            status=order.status,
            subtotal_ex_vat=order.subtotal_ex_vat,
            vat_amount=order.vat_amount,
            total_inc_vat=order.total_inc_vat,
            amount_paid=order.amount_paid,
            balance=balance,
            notes=order.notes,
            lines=[
                SalesOrderLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    our_ref=line.sku.our_ref,
                    name=line.sku.name,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    description=line.description,
                    notes=line.notes,
                    held_qty=line.held_qty,
                    hold_location_id=line.hold_location_id,
                )
                for line in order.lines
            ],
            payments=[
                SalesOrderPaymentResponse(
                    id=payment.id,
                    amount=payment.amount,
                    tender=payment.tender,
                    paid_on=payment.paid_on,
                )
                for payment in order.payments
            ],
            created_at=order.created_at,
            updated_at=order.updated_at,
        )
