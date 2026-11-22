from __future__ import annotations

import datetime
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crud.customer import CustomerCRUD
from app.services.party_archive import assert_customer_active
from app.services.sellability import assert_sku_sellable
from app.services.sku_archive import SkuArchiveService
from app.services.archive_documents import assert_operational_document, source_document_flags
from app.crud.location import LocationCRUD
from app.crud.ops_commerce_orders import OpsCommerceOrdersCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sales_order import SalesOrderCRUD
from app.crud.sku import SkuCRUD
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.ops_commerce_order import OpsCommerceOrder
from app.models.ops_commerce_refund import OpsCommerceRefund
from app.models.quote import Quote, QuoteStatus
from app.models.sales_order import (
    SalesOrder,
    SalesOrderLine,
    SalesOrderPayment,
    SalesOrderStatus,
)
from app.models.tax_invoice import InvoiceLine
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.ops_commerce_order import StorefrontPaidOrder
from app.schemas.page import Page, PageParams
from app.schemas.quote import QuoteAccept
from app.schemas.sale_line_pricing import SalePricePreview
from app.schemas.sales_order import (
    SalesOrderConfirm,
    SalesOrderCreate,
    SalesOrderLineResponse,
    SalesOrderListItem,
    SalesOrderPaymentCreate,
    SalesOrderPaymentResponse,
    SalesOrderResponse,
)
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import (
    CODE_BANK,
    CODE_DEPOSITS,
    CODE_INVENTORY,
    LedgerPostingService,
)
from app.services.pricing import shows_prices_including_vat
from app.services.sale_line_pricing import (
    PricingAuthority,
    SaleLinePricing,
    SaleLineRequest,
    document_totals,
    line_amounts,
)
from app.services.stock_movements import StockCost, StockMovementService
from app.services.suspect_price import annotate_line_warnings
from app.services.stocktakes import StocktakeService
from app.services.tax_invoice_issue import Deposits, TaxInvoiceIssue
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work

OPEN_STOREFRONT_REFUND_STATES = ("requested", "dispatching", "unknown", "pending", "needs_review")


class SalesOrdersService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SalesOrderCRUD(db)
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

    async def get(
        self,
        sales_order_id: uuid.UUID,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> SalesOrderResponse:
        return await self._to_response(await self._get_or_404(sales_order_id), viewer_user_id)

    async def create_draft(
        self,
        data: SalesOrderCreate,
        *,
        user_id: Optional[uuid.UUID] = None,
    ) -> SalesOrderResponse:
        customer = await self._require_customer(data.customer_id)
        assert_customer_active(customer)
        line_models, priced = await self._build_line_models(customer, data.lines, user_id)
        order = SalesOrder(
            so_number="",
            customer_id=customer.id,
            hold_stock=False,
            awaiting_stock=False,
            status=SalesOrderStatus.DRAFT,
            subtotal_ex_vat=priced.subtotal_ex_vat,
            vat_amount=priced.vat_amount,
            total_inc_vat=priced.total_inc_vat,
            vat_rate=priced.vat_rate,
            amount_paid=Decimal(0),
            notes=data.notes,
            prices_include_vat=shows_prices_including_vat(customer),
            created_by_user_id=user_id,
            lines=line_models,
        )
        async with unit_of_work(self.db):
            order.so_number = await self.crud.get_next_so_number()
            await self.crud.add_and_flush(order)
        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def create_from_quote(
        self,
        quote: Quote,
        data: QuoteAccept,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        existing = await self.crud.get_by_quote_id(quote.id)
        if existing is not None:
            raise ConflictError("Quote already has a sales order")
        # The quote's list unit, discount and VAT rate carry over; the order totals its own
        # lines with the one line rule, so its invoice adds up to what the order charged.
        line_models = [
            SalesOrderLine(
                sku_id=line.sku_id,
                qty=line.qty,
                unit_ex_vat=line.unit_ex_vat,
                discount_percent=line.discount_percent,
                description=line.description,
                notes=line.notes,
                price_warning=line.price_warning,
                held_qty=0,
            )
            for line in quote.lines
        ]
        subtotal, vat_amount, total_inc = document_totals(
            ((line.unit_ex_vat, line.qty, line.discount_percent) for line in line_models),
            quote.vat_rate,
        )
        order = SalesOrder(
            so_number="",
            customer_id=quote.customer_id,
            quote_id=quote.id,
            location_id=data.location_id,
            hold_stock=False,
            awaiting_stock=False,
            status=SalesOrderStatus.OPEN,
            subtotal_ex_vat=subtotal,
            vat_amount=vat_amount,
            total_inc_vat=total_inc,
            vat_rate=quote.vat_rate,
            prices_include_vat=quote.prices_include_vat,
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
        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def confirm(
        self,
        sales_order_id: uuid.UUID,
        data: SalesOrderConfirm,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        order = await self._get_or_404(sales_order_id, for_update=True)
        assert_operational_document(order)
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
        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def add_payment(
        self,
        sales_order_id: uuid.UUID,
        data: SalesOrderPaymentCreate,
        user_id: uuid.UUID,
    ) -> SalesOrderResponse:
        order = await self._require_open(sales_order_id, for_update=True)
        new_total = order.amount_paid + data.amount
        if new_total > order.total_inc_vat:
            raise ValidationError("Payment would exceed sales order total")
        async with unit_of_work(self.db):
            await self._add_deposit_locked(order, data)
        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def cancel(self, sales_order_id: uuid.UUID, user_id: uuid.UUID) -> SalesOrderResponse:
        order = await self._get_or_404(sales_order_id, for_update=True)
        assert_operational_document(order)
        storefront_handoff = await self.db.scalar(
            select(OpsCommerceOrder.id).where(
                OpsCommerceOrder.sales_order_id == sales_order_id,
                OpsCommerceOrder.channel == "storefront",
            )
        )
        if storefront_handoff is not None:
            raise ConflictError("Storefront orders require the verified refund workflow to cancel")
        if order.status not in (
            SalesOrderStatus.DRAFT,
            SalesOrderStatus.OPEN,
            SalesOrderStatus.AWAITING_STOCK,
        ):
            raise ConflictError("Sales order cannot be cancelled")
        async with unit_of_work(self.db):
            await self._release_held_stock(
                order,
                user_id,
                note=f"Sales order {order.so_number} cancel restock",
            )
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
        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def complete_storefront_cancel_after_refund(
        self, order: SalesOrder, user_id: uuid.UUID
    ) -> None:
        """Release held stock after verified refund; caller owns order lock and transaction."""
        if order.invoice_id is not None or order.status not in (
            SalesOrderStatus.OPEN,
            SalesOrderStatus.AWAITING_STOCK,
        ):
            raise ConflictError("Storefront sales order is no longer eligible for cancellation")
        if order.amount_paid != 0:
            raise ConflictError(
                "Storefront order must have a zero deposit balance before cancellation"
            )
        await self._release_held_stock(
            order,
            user_id,
            note=f"Storefront sales order {order.so_number} cancel restock",
        )
        order.status = SalesOrderStatus.CANCELLED
        order.hold_stock = False

    async def _release_held_stock(
        self, order: SalesOrder, user_id: uuid.UUID, *, note: str
    ) -> None:
        location_ids = {
            line.hold_location_id for line in order.lines if line.hold_location_id is not None
        }
        for location_id in location_ids:
            await self.stocktakes.assert_location_unlocked(location_id)
        for line in order.lines:
            if line.held_qty <= 0 or line.hold_location_id is None:
                continue
            held = await self._held_cost(line)
            if held.unit_cost_zar is None:
                raise ValidationError("unit cost required")
            await self.stock_movements.apply_incoming_qty(
                sku_id=line.sku_id,
                location_id=line.hold_location_id,
                qty=line.held_qty,
                unit_cost_zar=held.unit_cost_zar,
                user_id=user_id,
                source=UnitCostAuditSource.SALES_ORDER,
                note=note,
            )
            line.held_qty = 0

    async def _held_cost(self, line: SalesOrderLine) -> StockCost:
        """The cost the held stock left the shelf at; older holds without one use today's average."""
        unit_cost = line.hold_unit_cost_zar
        if unit_cost is None and line.hold_location_id is not None:
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id, line.hold_location_id
            )
            unit_cost = loc_stock.unit_cost_zar if loc_stock is not None else None
        return StockCost(Decimal(line.held_qty), unit_cost)

    async def _storefront_tax_snapshot(
        self, order: SalesOrder
    ) -> Optional[list[tuple[Decimal, Decimal, Decimal]]]:
        handoff = await OpsCommerceOrdersCRUD(self.db).get_by_sales_order(order.id)
        if handoff is None:
            return None
        paid_order = StorefrontPaidOrder.model_validate(handoff.payload)
        by_identity = {
            f"Storefront line {line.external_line_id}": line for line in paid_order.lines
        }
        if len(order.lines) != len(by_identity) or {line.notes for line in order.lines} != set(
            by_identity
        ):
            raise ConflictError("Storefront order lines no longer match the paid snapshot")
        snapshot: list[tuple[Decimal, Decimal, Decimal]] = []
        for line in order.lines:
            paid_line = by_identity[line.notes]
            if (
                line.sku_id != paid_line.source_sku_id
                or line.qty != paid_line.quantity
                or line.unit_ex_vat != Decimal(paid_line.unit_ex_minor_zar) / 100
            ):
                raise ConflictError("Storefront order lines no longer match the paid snapshot")
            snapshot.append(
                (
                    Decimal(paid_line.ex_minor_zar) / 100,
                    Decimal(paid_line.vat_minor_zar) / 100,
                    Decimal(paid_line.total_minor_zar) / 100,
                )
            )
        snapshot.append(
            (
                Decimal(paid_order.totals.delivery_ex_minor_zar) / 100,
                Decimal(paid_order.totals.delivery_tax_minor_zar) / 100,
                Decimal(paid_order.totals.delivery_total_minor_zar) / 100,
            )
        )
        return snapshot

    async def create_remainder_invoice(
        self,
        sales_order_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        stock_source: UnitCostAuditSource = UnitCostAuditSource.SALES_ORDER,
        before_commit: Optional[Callable[[], Awaitable[None]]] = None,
    ) -> SalesOrderResponse:
        order = await self._require_open(sales_order_id, for_update=True)
        if order.invoice_id is not None:
            raise ConflictError("Sales order already invoiced")
        unresolved_storefront_refund_id = await self.db.scalar(
            select(OpsCommerceRefund.id)
            .join(OpsCommerceOrder, OpsCommerceOrder.id == OpsCommerceRefund.handoff_id)
            .where(
                OpsCommerceOrder.sales_order_id == order.id,
                OpsCommerceOrder.channel == "storefront",
                OpsCommerceRefund.status.in_(OPEN_STOREFRONT_REFUND_STATES),
            )
            .limit(1)
        )
        if unresolved_storefront_refund_id is not None:
            raise ConflictError("Resolve the Storefront refund before invoicing the sales order")
        tax_snapshot = await self._storefront_tax_snapshot(order)
        if tax_snapshot is not None:
            stock_source = UnitCostAuditSource.STOREFRONT
        issue_date = datetime.date.today()

        invoice_line_models: list[InvoiceLine] = []
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        for index, line in enumerate(order.lines):
            if tax_snapshot is None:
                ex_vat, line_vat, inc_vat = line_amounts(
                    line.unit_ex_vat, line.qty, line.discount_percent, order.vat_rate
                )
            else:
                if len(tax_snapshot) != len(order.lines) + 1:
                    raise ValidationError("Storefront tax snapshot does not match order lines")
                ex_vat, line_vat, inc_vat = tax_snapshot[index]
                if ex_vat + line_vat != inc_vat:
                    raise ValidationError("Storefront tax snapshot line does not balance")
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            invoice_line_models.append(
                InvoiceLine(
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    discount_percent=line.discount_percent,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=line.sku_id,
                    price_warning=line.price_warning,
                )
            )

        if tax_snapshot is not None:
            delivery_ex, delivery_vat, delivery_inc = tax_snapshot[-1]
            if delivery_ex + delivery_vat != delivery_inc:
                raise ValidationError("Storefront delivery tax snapshot does not balance")
            if delivery_ex or delivery_vat or delivery_inc:
                subtotal += delivery_ex
                vat_total += delivery_vat
                total_inc += delivery_inc
                # ponytail: delivery has no SKU, so it posts to CODE_SALES ("4000"), as it
                # always has; a delivery income account is its own decision.
                invoice_line_models.append(
                    InvoiceLine(
                        description="Storefront delivery",
                        qty=1,
                        unit_ex_vat=delivery_ex,
                        ex_vat=delivery_ex,
                        inc_vat=delivery_inc,
                        vat_amount=delivery_vat,
                        sort_order=len(invoice_line_models),
                        sku_id=None,
                    )
                )
            if (
                subtotal != order.subtotal_ex_vat
                or vat_total != order.vat_amount
                or total_inc != order.total_inc_vat
            ):
                raise ValidationError("Storefront tax snapshot does not match the paid order")

        outgoing_needed = [line for line in order.lines if line.held_qty < line.qty]
        if outgoing_needed:
            location_id = order.location_id
            if location_id is None:
                raise ValidationError("Location is required to issue remaining stock")
            await self.stocktakes.assert_location_unlocked(location_id)

        async with unit_of_work(self.db):
            invoice = await TaxInvoiceIssue(self.db).issue(
                customer=order.customer,
                issue_date=issue_date,
                lines=invoice_line_models,
                vat_rate=order.vat_rate,
                prices_include_vat=order.prices_include_vat,
                memo="Sales order tax invoice",
                actor_user_id=user_id,
                deposits=Deposits(
                    source_id=order.id,
                    memo=f"Apply sales order deposits {order.so_number}",
                    amount=order.amount_paid,
                ),
            )

            total_cogs = Decimal(0)
            cogs_parts: list[tuple[str, Decimal, Decimal]] = []
            # Order lines come first in invoice_line_models; delivery, if any, follows.
            for line, invoice_line in zip(order.lines, invoice_line_models):
                # A line is either held in full or not at all (_apply_hold).
                if line.held_qty < line.qty:
                    assert order.location_id is not None
                    sold = await self.stock_movements.apply_outgoing_qty(
                        sku_id=line.sku_id,
                        location_id=order.location_id,
                        qty=line.qty - line.held_qty,
                        user_id=user_id,
                        source=stock_source,
                        note=f"Sales order {order.so_number} remainder",
                    )
                    line.held_qty = line.qty
                    line.hold_location_id = order.location_id
                else:
                    sold = await self._held_cost(line)
                line_cogs = sold.total_zar
                invoice_line.unit_cost_zar = sold.unit_cost_zar
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
            order.awaiting_stock = False
            if before_commit is not None:
                await before_commit()

        return await self._to_response(await self._get_or_404(order.id), user_id)

    async def _apply_hold(
        self,
        order: SalesOrder,
        location_id: Optional[uuid.UUID],
        user_id: uuid.UUID,
        *,
        eligible_line_ids: Optional[set[uuid.UUID]] = None,
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
            # A paid made-to-order line is an operational promise, not stock to
            # reserve from a warehouse. Callers may hold only the stocked lines.
            if eligible_line_ids is not None and line.id not in eligible_line_ids:
                any_unheld = True
                continue
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                line.sku_id,
                location_id,
            )
            on_hand = loc_stock.on_hand if loc_stock is not None else 0
            if loc_stock is None or loc_stock.unit_cost_zar is None or on_hand < line.qty:
                any_unheld = True
                continue
            held = await self.stock_movements.apply_outgoing_qty(
                sku_id=line.sku_id,
                location_id=location_id,
                qty=line.qty,
                user_id=user_id,
                source=UnitCostAuditSource.SALES_ORDER,
                note=f"Sales order {order.so_number} hold",
            )
            line.held_qty = line.qty
            line.hold_location_id = location_id
            line.hold_unit_cost_zar = held.unit_cost_zar
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
        user_id: Optional[uuid.UUID],
    ) -> tuple[list[SalesOrderLine], SalePricePreview]:
        await SkuArchiveService(self.db).lock_skus([line.sku_id for line in lines])
        skus = []
        for line in lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            assert_sku_sellable(sku)
            skus.append(sku)
        pricing = await SaleLinePricing.for_customer(
            self.db, customer, await PricingAuthority.of(self.db, user_id)
        )
        # Sales order lines carry no discount or price override.
        priced = await pricing.price(
            [SaleLineRequest(sku=sku, qty=line.qty) for sku, line in zip(skus, lines, strict=True)]
        )
        models = [
            SalesOrderLine(
                sku_id=sku.id,
                qty=line.qty,
                unit_ex_vat=price.unit_ex_vat,
                discount_percent=price.discount_percent,
                description=sku.name,
                notes=getattr(line, "notes", None),
                price_warning=price.price_warning,
                held_qty=0,
            )
            for sku, line, price in zip(skus, lines, priced.lines, strict=True)
        ]
        return models, priced

    async def _require_customer(self, customer_id: uuid.UUID):
        customer = await self.customer_crud.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        return customer

    async def _get_or_404(
        self, sales_order_id: uuid.UUID, *, for_update: bool = False
    ) -> SalesOrder:
        order = await self.crud.get_by_id(sales_order_id, for_update=for_update)
        if order is None:
            raise NotFoundError("Sales order not found")
        return order

    async def _require_open(
        self, sales_order_id: uuid.UUID, *, for_update: bool = False
    ) -> SalesOrder:
        order = await self._get_or_404(sales_order_id, for_update=for_update)
        assert_operational_document(order)
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
            **source_document_flags(order),
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

    async def _to_response(
        self,
        order: SalesOrder,
        viewer_user_id: Optional[uuid.UUID] = None,
    ) -> SalesOrderResponse:
        balance = order.total_inc_vat - order.amount_paid
        response = SalesOrderResponse(
            **source_document_flags(order),
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
            vat_rate=order.vat_rate,
            amount_paid=order.amount_paid,
            balance=balance,
            notes=order.notes,
            prices_include_vat=order.prices_include_vat,
            lines=[
                SalesOrderLineResponse(
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
        await annotate_line_warnings(
            self.db,
            response.lines,
            viewer_user_id=viewer_user_id,
            inclusive_vat_rate=order.vat_rate if order.prices_include_vat else None,
        )
        return response
