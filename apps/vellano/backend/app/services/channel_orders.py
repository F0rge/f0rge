from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.channel import (
    ChannelListingCRUD,
    ChannelOrderCRUD,
    SalesChannelCRUD,
)
from app.crud.customer import CustomerCRUD
from app.crud.payment import PaymentCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD, UserCRUD
from app.models.channel import (
    CHANNEL_SLUG_MANUAL,
    CHANNEL_SLUG_SHOPIFY,
    ChannelAtpMode,
    ChannelListing,
    ChannelOrder,
    ChannelOrderStatus,
)
from app.models.customer import Customer
from app.crud.credit_note import CreditNoteCRUD
from app.models.delivery import DeliverySourceType, DeliveryStatus
from app.models.journal import JournalDocumentType
from app.models.payment import Payment, PaymentDirection
from app.models.stock_return import StockReturnDisposition, StockReturnReason
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User, UserRole
from app.schemas.channel import ChannelOrderCreate, ChannelOrderLineIn, ChannelOrderResponse
from app.schemas.delivery import DeliveryComplete, DeliveryCreate
from app.schemas.stock_return import StockReturnCreate, StockReturnLineCreate
from app.services.books_events import BooksEventService
from app.services.books_periods import assert_date_postable
from app.services.category_posting import CategoryPostingService
from app.services.channel_atp import ChannelAtpService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_INVENTORY,
    CODE_SHOPIFY_CLEARING,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.settings import parse_pick_priority
from app.services.deliveries import DeliveriesService
from app.services.payment_terms import compute_due_date
from app.services.pricing import resolve_unit_ex_vat
from app.services.pick_allocator import ComponentNeed, LocationStockRow, allocate
from app.services.stock_movements import StockMovementService
from app.services.stock_returns import StockReturnsService
from app.services.stocktakes import StocktakeService
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from app.services.vat import CENT, ex_to_inc, inc_to_ex
from app.models.books_event import BooksDocumentType, BooksEventAction
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class ChannelOrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.orders = ChannelOrderCRUD(db)
        self.channels = SalesChannelCRUD(db)
        self.listings = ChannelListingCRUD(db)
        self.skus = SkuCRUD(db)
        self.customers = CustomerCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.payment_crud = PaymentCRUD(db)
        self.location_stock = LocationStockCRUD(db)
        self.bom_crud = SkuBomLineCRUD(db)
        self.atp = ChannelAtpService(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)
        self.events = BooksEventService(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)
        self.users = UserCRUD(db)
        self.teams = TeamCRUD(db)
        self.settings_crud = TeamSettingsCRUD(db)

    async def list_page(
        self,
        limit: int,
        offset: int,
        q: Optional[str] = None,
        status: Optional[ChannelOrderStatus] = None,
        channel: Optional[str] = None,
    ) -> tuple[list[ChannelOrderResponse], int]:
        channel_id = None
        if channel:
            row = await self.channels.get_by_slug(channel)
            if row is None:
                raise NotFoundError("Channel not found")
            channel_id = row.id
        rows, total = await self.orders.list_page(
            limit=limit,
            offset=offset,
            q=q,
            status=status,
            channel_id=channel_id,
        )
        return [self._to_response(row) for row in rows], total

    async def get(self, order_id: uuid.UUID) -> ChannelOrderResponse:
        row = await self.orders.get_by_id(order_id)
        if row is None:
            raise NotFoundError("Channel order not found")
        return self._to_response(row)

    async def ingest(
        self,
        data: ChannelOrderCreate,
        user_id: Optional[uuid.UUID],
        process: bool = True,
    ) -> ChannelOrderResponse:
        channel = await self.channels.get_by_slug(data.channel)
        if channel is None:
            raise NotFoundError("Channel not found")
        actor_id = user_id or await self.actor_user_id()
        existing = await self.orders.get_by_external(channel.id, data.external_id)
        if existing is not None:
            if process and existing.status in (
                ChannelOrderStatus.RECEIVED,
                ChannelOrderStatus.NEEDS_MAPPING,
                ChannelOrderStatus.FAILED,
            ):
                return await self.process(existing.id, actor_id)
            return self._to_response(existing)

        order = ChannelOrder(
            channel_id=channel.id,
            external_order_id=data.external_id,
            status=ChannelOrderStatus.RECEIVED,
            email=data.email,
            payload=data.payload or data.model_dump(mode="json"),
            allocations=[],
            shopify_fulfillment_order_id=data.shopify_fulfillment_order_id,
        )
        async with unit_of_work(self.db):
            await self.orders.add_and_flush(order)
        if process and data.paid:
            return await self.process(order.id, actor_id)
        return self._to_response(await self._reload(order.id))

    async def process(
        self, order_id: uuid.UUID, user_id: Optional[uuid.UUID]
    ) -> ChannelOrderResponse:
        order = await self.orders.lock_by_id(order_id)
        if order is None:
            raise NotFoundError("Channel order not found")
        if order.status == ChannelOrderStatus.POSTED:
            return self._to_response(order)
        if order.status in (ChannelOrderStatus.CANCELLED, ChannelOrderStatus.REFUNDED):
            raise ConflictError("Order is already cancelled")

        actor_id = user_id or await self.actor_user_id()
        payload = order.payload or {}
        lines_in = self._lines_from_payload(payload)
        mapped, unmapped = await self._map_lines(order.channel.slug, lines_in)
        if unmapped:
            async with unit_of_work(self.db):
                order.status = ChannelOrderStatus.NEEDS_MAPPING
                order.error_message = "Unmapped SKUs: " + ", ".join(unmapped)
            return self._to_response(await self._reload(order.id))

        try:
            await self._post_sale(order, mapped, payload, actor_id)
        except (ConflictError, ValidationError, NotFoundError) as exc:
            async with unit_of_work(self.db):
                order.status = ChannelOrderStatus.FAILED
                order.error_message = str(getattr(exc, "detail", None) or exc)
            return self._to_response(await self._reload(order.id))
        return self._to_response(await self._reload(order.id))

    async def fulfill(self, order_id: uuid.UUID, user_id: uuid.UUID) -> ChannelOrderResponse:
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Channel order not found")
        if order.status != ChannelOrderStatus.POSTED:
            raise ConflictError("Only posted channel orders can be fulfilled")
        if order.delivery_id is None:
            if order.invoice_id is None:
                raise ConflictError("Channel order has no delivery")
            location_id = order.invoice.location_id if order.invoice is not None else None
            if location_id is None and order.allocations:
                location_id = uuid.UUID(str(order.allocations[0]["location_id"]))
            if location_id is None:
                raise ConflictError("Channel order has no delivery")
            await self._ensure_delivery(order, order.invoice_id, location_id, user_id)
            order = await self._reload(order.id)
        if order.delivery_id is None:
            raise ConflictError("Channel order has no delivery")
        deliveries = DeliveriesService(self.db)
        delivery = await deliveries.get(order.delivery_id)
        if delivery.status == DeliveryStatus.DRAFT:
            await deliveries.pack(order.delivery_id)
            delivery = await deliveries.get(order.delivery_id)
        if delivery.status == DeliveryStatus.PACKED:
            await deliveries.complete(order.delivery_id, DeliveryComplete())
        if (
            order.shopify_fulfillment_order_id is None
            and order.channel.slug == CHANNEL_SLUG_SHOPIFY
        ):
            fo_id = await self._resolve_fulfillment_order_id(order)
            if fo_id:
                async with unit_of_work(self.db):
                    order.shopify_fulfillment_order_id = fo_id
        from app.services.channel_outbox import ChannelOutboxService

        await ChannelOutboxService(self.db).enqueue_fulfillment(order.id)
        await ChannelOutboxService(self.db).drain(limit=20)
        return self._to_response(await self._reload(order.id))

    async def cancel(self, order_id: uuid.UUID, user_id: uuid.UUID) -> ChannelOrderResponse:
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Channel order not found")
        if order.status in (ChannelOrderStatus.CANCELLED, ChannelOrderStatus.REFUNDED):
            return self._to_response(order)
        if order.status != ChannelOrderStatus.POSTED:
            async with unit_of_work(self.db):
                order.status = ChannelOrderStatus.CANCELLED
            return self._to_response(await self._reload(order.id))

        allocations = list(order.allocations or [])
        invoice = None
        if order.invoice_id is not None:
            invoice = await self.invoice_crud.get_by_id(order.invoice_id)
        if invoice is not None:
            existing_cn = await CreditNoteCRUD(self.db).get_by_invoice_id(invoice.id)
            if existing_cn is None:
                await self._credit_write_off(invoice, order, user_id)
        total_cogs = Decimal(0)
        cogs_parts: list[tuple[str, Decimal, Decimal]] = []
        for alloc in allocations:
            sku_id = uuid.UUID(str(alloc["sku_id"]))
            qty = int(alloc["qty"])
            unit_cost = Decimal(str(alloc["unit_cost_zar"]))
            await self.stock_movements.apply_incoming_qty(
                sku_id=sku_id,
                location_id=uuid.UUID(str(alloc["location_id"])),
                qty=qty,
                unit_cost_zar=unit_cost,
                user_id=user_id,
                source=UnitCostAuditSource.CHANNEL,
                note=f"Channel refund {order.external_order_id}",
            )
            line_cogs = (unit_cost * qty).quantize(CENT, rounding=ROUND_HALF_UP)
            total_cogs += line_cogs
            sku = await self.skus.get_by_id(sku_id)
            if sku is not None:
                cogs_code = await self.category_posting.cogs_code_for_sku(sku)
                cogs_parts.append((cogs_code, Decimal(0), line_cogs))
        credit_note = None
        if invoice is not None:
            credit_note = await CreditNoteCRUD(self.db).get_by_invoice_id(invoice.id)
        async with unit_of_work(self.db):
            if credit_note is not None and total_cogs > 0 and cogs_parts:
                await self.posting.post(
                    JournalDocumentType.CREDIT_NOTE,
                    credit_note.id,
                    f"COGS reverse for channel refund {order.external_order_id}",
                    self.category_posting.collapse(
                        [
                            (CODE_INVENTORY, total_cogs, Decimal(0)),
                            *cogs_parts,
                        ]
                    ),
                    entry_date=credit_note.issue_date,
                )
            order.status = ChannelOrderStatus.REFUNDED
        return self._to_response(await self._reload(order.id))

    async def _post_sale(
        self,
        order: ChannelOrder,
        mapped: list[tuple[Any, ChannelOrderLineIn]],
        payload: dict,
        user_id: uuid.UUID,
    ) -> None:
        team = await self.teams.get_first()
        if team is None:
            raise NotFoundError("Team not found")
        team_settings = await self.settings_crud.get_or_create_for_team(team.id)
        customer = await self._upsert_customer(order.email, payload.get("customer_name"))
        sale_date = datetime.date.today()
        await assert_date_postable(self.db, sale_date)

        shopify_gid = payload.get("shopify_location_gid")
        mode, _ = await self.atp.mode_and_location()
        primary_location = await self.atp.resolve_sale_location(shopify_gid)

        line_models: list[InvoiceLine] = []
        cogs_parts: list[tuple[str, Decimal, Decimal]] = []
        sales_parts: list[tuple[str, Decimal, Decimal]] = []
        decrements: list[tuple[uuid.UUID, uuid.UUID, int, Decimal]] = []
        reserved: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        total_cogs = Decimal(0)

        for index, (sku, line) in enumerate(mapped):
            bom = await self.bom_crud.list_by_parent(sku.id)
            if line.unit_inc_vat is not None:
                unit_ex = inc_to_ex(line.unit_inc_vat)
            else:
                unit_ex = await resolve_unit_ex_vat(self.db, sku, customer)
            ex_vat = (Decimal(line.qty) * unit_ex).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            sales_code = await self.category_posting.sales_code_for_sku(sku)
            sales_parts.append((sales_code, Decimal(0), ex_vat))
            line_models.append(
                InvoiceLine(
                    description=line.name or sku.name,
                    qty=line.qty,
                    unit_ex_vat=unit_ex,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=sku.id,
                )
            )
            if bom:
                needs = [
                    ComponentNeed(sku_id=row.component_sku_id, qty_needed=row.qty * line.qty)
                    for row in bom
                ]
            else:
                needs = [ComponentNeed(sku_id=sku.id, qty_needed=line.qty)]
            allocations = await self._allocate_needs(needs, mode, primary_location.id, reserved)
            line_cogs = Decimal(0)
            for alloc_sku_id, alloc_location_id, qty in allocations:
                loc_stock = await self.location_stock.get_by_sku_and_location(
                    alloc_sku_id, alloc_location_id
                )
                if loc_stock is None or loc_stock.unit_cost_zar is None:
                    raise ConflictError("No unit cost for channel sale allocation")
                cost = loc_stock.unit_cost_zar
                line_cogs += (cost * qty).quantize(CENT, rounding=ROUND_HALF_UP)
                decrements.append((alloc_sku_id, alloc_location_id, qty, cost))
                key = (alloc_sku_id, alloc_location_id)
                reserved[key] = reserved.get(key, 0) + qty
            total_cogs += line_cogs
            cogs_code = await self.category_posting.cogs_code_for_sku(sku)
            cogs_parts.append((cogs_code, line_cogs, Decimal(0)))

        if subtotal <= 0:
            raise ValidationError("Sale total must be positive")

        due_date = compute_due_date(sale_date, customer, team_settings)
        source = order.channel.slug
        locations_to_lock = {item[1] for item in decrements}
        for location_id in locations_to_lock:
            await self.stocktakes.assert_location_unlocked(location_id)

        async with unit_of_work(self.db):
            for sku, line in mapped:
                await self._touch_listing(order.channel_id, sku, line)
            invoice_number = await self.invoice_crud.get_next_invoice_number()
            payment_number = await self.payment_crud.get_next_payment_number()
            invoice = TaxInvoice(
                invoice_number=invoice_number,
                customer_id=customer.id,
                issue_date=sale_date,
                due_date=due_date,
                subtotal_ex_vat=subtotal,
                vat_amount=vat_total,
                total_inc_vat=total_inc,
                amount_paid=Decimal(0),
                source=source,
                location_id=primary_location.id,
                lines=line_models,
            )
            payment = Payment(
                payment_number=payment_number,
                direction=PaymentDirection.IN,
                invoice_id=None,
                amount=total_inc,
                currency="ZAR",
                fx_to_zar=Decimal("1"),
                amount_zar=total_inc,
                fx_gain_loss_zar=Decimal(0),
                paid_on=sale_date,
                tender="shopify" if source == CHANNEL_SLUG_SHOPIFY else "eft",
            )
            await self.invoice_crud.add_and_flush(invoice)
            payment.invoice_id = invoice.id
            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Channel tax invoice {invoice_number}",
                self.category_posting.collapse(
                    [
                        (CODE_AR, total_inc, Decimal(0)),
                        *sales_parts,
                        (CODE_VAT, Decimal(0), vat_total),
                    ]
                ),
                entry_date=sale_date,
            )
            await self.payment_crud.add_and_flush(payment)
            cash_code = CODE_SHOPIFY_CLEARING if source == CHANNEL_SLUG_SHOPIFY else CODE_BANK
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Channel payment {payment_number}",
                [
                    (cash_code, total_inc, Decimal(0)),
                    (CODE_AR, Decimal(0), total_inc),
                ],
                entry_date=sale_date,
            )
            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for channel sale {invoice_number}",
                    self.category_posting.collapse(
                        [
                            *cogs_parts,
                            (CODE_INVENTORY, Decimal(0), total_cogs),
                        ]
                    ),
                    entry_date=sale_date,
                )
            snapshot = []
            for sku_id, location_id, qty, cost in decrements:
                await self.stock_movements.apply_outgoing_qty(
                    sku_id=sku_id,
                    location_id=location_id,
                    qty=qty,
                    user_id=user_id,
                    source=UnitCostAuditSource.CHANNEL,
                    note=f"Channel sale {order.external_order_id}",
                )
                snapshot.append(
                    {
                        "sku_id": str(sku_id),
                        "location_id": str(location_id),
                        "qty": qty,
                        "unit_cost_zar": str(cost),
                    }
                )
            invoice.amount_paid = total_inc
            order.invoice_id = invoice.id
            order.customer_id = customer.id
            order.allocations = snapshot
            order.status = ChannelOrderStatus.POSTED
            order.error_message = None
            await self.events.record(
                BooksDocumentType.INVOICE,
                invoice.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
                note=f"channel:{source}:{order.external_order_id}",
            )
            await self.events.record(
                BooksDocumentType.PAYMENT,
                payment.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
            )

        await self._ensure_delivery(order, invoice.id, primary_location.id, user_id)

    async def _ensure_delivery(
        self,
        order: ChannelOrder,
        invoice_id: uuid.UUID,
        location_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if order.delivery_id is not None:
            return
        deliveries = DeliveriesService(self.db)
        delivery_id = None
        try:
            delivery = await deliveries.create(
                DeliveryCreate(
                    source_type=DeliverySourceType.INVOICE,
                    invoice_id=invoice_id,
                    location_id=location_id,
                ),
                user_id,
            )
            delivery_id = delivery.id
        except (ConflictError, ValidationError):
            existing = await deliveries.crud.get_active_by_invoice_id(invoice_id)
            if existing is not None:
                delivery_id = existing.id
        if delivery_id is None:
            return
        async with unit_of_work(self.db):
            order.delivery_id = delivery_id

    async def _allocate_needs(
        self,
        needs: list[ComponentNeed],
        mode: ChannelAtpMode,
        primary_location_id: uuid.UUID,
        reserved: dict[tuple[uuid.UUID, uuid.UUID], int],
    ) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
        if mode != ChannelAtpMode.POOLED:
            result: list[tuple[uuid.UUID, uuid.UUID, int]] = []
            for need in needs:
                available = await self._available_at(need.sku_id, primary_location_id, reserved)
                if available < need.qty_needed:
                    raise ConflictError("Insufficient on-hand quantity")
                result.append((need.sku_id, primary_location_id, need.qty_needed))
            return result

        from app.crud.location import LocationCRUD

        locations = await LocationCRUD(self.db).list_all()
        sku_ids = [need.sku_id for need in needs]
        stocks = await self.location_stock.list_for_sku_ids(sku_ids)
        by_key = {(row.sku_id, row.location_id): row for row in stocks}
        rows: list[LocationStockRow] = []
        included = set(await self.atp.included_location_ids())
        for location in locations:
            if location.id not in included:
                continue
            for sku_id in sku_ids:
                stock = by_key.get((sku_id, location.id))
                on_hand = stock.on_hand if stock is not None else 0
                on_hand -= reserved.get((sku_id, location.id), 0)
                rows.append(
                    LocationStockRow(
                        location_id=location.id,
                        sku_id=sku_id,
                        on_hand=max(on_hand, 0),
                        location_type=location.type.value,
                        location_name=location.name,
                        is_archived=location.is_archived,
                    )
                )
        settings = await self.atp._settings()
        allocated = allocate(
            needs,
            rows,
            bool(settings.always_prefer_warehouse),
            parse_pick_priority(settings.pick_priority),
        )
        if any(line.qty_short > 0 for line in allocated.lines):
            raise ConflictError("Insufficient on-hand quantity")
        result = []
        for line in allocated.lines:
            for item in line.allocations:
                result.append((item.sku_id, item.location_id, item.qty))
        return result

    async def _available_at(
        self,
        sku_id: uuid.UUID,
        location_id: uuid.UUID,
        reserved: dict[tuple[uuid.UUID, uuid.UUID], int],
    ) -> int:
        loc_stock = await self.location_stock.get_by_sku_and_location(sku_id, location_id)
        on_hand = loc_stock.on_hand if loc_stock is not None else 0
        return on_hand - reserved.get((sku_id, location_id), 0)

    async def _map_lines(
        self, channel_slug: str, lines: list[ChannelOrderLineIn]
    ) -> tuple[list[tuple[Any, ChannelOrderLineIn]], list[str]]:
        channel = await self.channels.get_by_slug(channel_slug)
        if channel is None:
            raise NotFoundError("Channel not found")
        mapped: list[tuple[Any, ChannelOrderLineIn]] = []
        unmapped: list[str] = []
        for line in lines:
            sku = None
            if line.sku_id is not None:
                sku = await self.skus.get_by_id(line.sku_id)
            if sku is None and line.variant_id:
                listing = await self.listings.get_by_variant(channel.id, line.variant_id)
                if listing is not None:
                    sku = listing.sku
            if sku is None and line.sku:
                listing = await self.listings.get_by_external_sku(channel.id, line.sku)
                if listing is not None:
                    sku = listing.sku
                if sku is None:
                    sku = await self.skus.get_by_our_ref(line.sku)
                if sku is None:
                    sku = await self.skus.get_by_our_barcode(line.sku)
            if sku is None:
                unmapped.append(line.sku or line.variant_id or line.name or "unknown")
            else:
                mapped.append((sku, line))
        return mapped, unmapped

    async def _touch_listing(self, channel_id: uuid.UUID, sku, line: ChannelOrderLineIn) -> None:
        existing = await self.listings.get_by_sku(channel_id, sku.id)
        if existing is None:
            await self.listings.add_and_flush(
                ChannelListing(
                    channel_id=channel_id,
                    sku_id=sku.id,
                    external_variant_id=line.variant_id,
                    external_inventory_item_id=line.inventory_item_id,
                    external_sku=line.sku or sku.our_ref,
                )
            )
            return
        if line.variant_id:
            existing.external_variant_id = line.variant_id
        if line.inventory_item_id:
            existing.external_inventory_item_id = line.inventory_item_id
        if line.sku:
            existing.external_sku = line.sku

    def _lines_from_payload(self, payload: dict) -> list[ChannelOrderLineIn]:
        raw_lines = payload.get("lines") or []
        parsed: list[ChannelOrderLineIn] = []
        for item in raw_lines:
            if isinstance(item, ChannelOrderLineIn):
                parsed.append(item)
                continue
            qty = int(item.get("qty") or item.get("quantity") or 0)
            if qty < 1:
                continue
            unit = item.get("unit_inc_vat")
            unit_inc: Optional[Decimal] = None
            if unit not in (None, ""):
                parsed_unit = Decimal(str(unit))
                if parsed_unit > 0:
                    unit_inc = parsed_unit
            parsed.append(
                ChannelOrderLineIn(
                    sku=item.get("sku"),
                    sku_id=item.get("sku_id"),
                    qty=qty,
                    unit_inc_vat=unit_inc,
                    variant_id=item.get("variant_id")
                    or (str(item["variant_id"]) if item.get("variant_id") else None),
                    inventory_item_id=item.get("inventory_item_id"),
                    name=item.get("name") or item.get("title"),
                )
            )
        if not parsed:
            raise ValidationError("Channel order has no lines")
        return parsed

    async def _upsert_customer(self, email: Optional[str], name: Optional[str]) -> Customer:
        if email:
            existing = (
                await self.db.execute(
                    select(Customer).where(Customer.email == email.strip()).limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            customer = Customer(
                name=(name or email).strip(),
                email=email.strip(),
                customer_type="retail",
            )
            await self.customers.add_and_flush(customer)
            return customer
        walk_in = (
            await self.db.execute(
                select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
            )
        ).scalar_one_or_none()
        if walk_in is None:
            raise NotFoundError("Walk-in customer not seeded")
        return walk_in

    async def _credit_write_off(
        self, invoice: TaxInvoice, order: ChannelOrder, user_id: uuid.UUID
    ) -> None:
        if not invoice.lines:
            return
        location_id = invoice.location_id
        if location_id is None and order.allocations:
            location_id = uuid.UUID(str(order.allocations[0]["location_id"]))
        if location_id is None:
            return
        service = StockReturnsService(self.db)
        created = await service.create(
            StockReturnCreate(
                invoice_id=invoice.id,
                location_id=location_id,
                reason=StockReturnReason.UNWANTED,
                disposition=StockReturnDisposition.WRITE_OFF,
                notes=f"Channel cancel {order.external_order_id}",
                lines=[
                    StockReturnLineCreate(invoice_line_id=line.id, sku_id=line.sku_id, qty=line.qty)
                    for line in invoice.lines
                    if line.qty > 0
                ],
            ),
            user_id,
        )
        await service.complete(created.id, user_id)

    async def actor_user_id(self) -> uuid.UUID:
        owner = (
            await self.db.execute(select(User).where(User.role == UserRole.OWNER.value).limit(1))
        ).scalar_one_or_none()
        if owner is None:
            raise NotFoundError("Owner user not found")
        return owner.id

    async def _resolve_fulfillment_order_id(self, order: ChannelOrder) -> Optional[str]:
        from app.services.channel_outbox import resolve_shopify_credentials
        from app.services.shopify_admin import ShopifyAdminClient

        channel = order.channel
        domain, token, _secret = resolve_shopify_credentials(channel)
        if not domain or not token:
            return None
        return await ShopifyAdminClient(domain, token).fulfillment_order_id_for_order(
            order.external_order_id
        )

    async def _reload(self, order_id: uuid.UUID) -> ChannelOrder:
        row = await self.orders.get_by_id(order_id)
        assert row is not None
        return row

    def _to_response(self, row: ChannelOrder) -> ChannelOrderResponse:
        invoice_number = None
        if row.invoice is not None:
            invoice_number = row.invoice.invoice_number
        return ChannelOrderResponse(
            id=row.id,
            channel=row.channel.slug if row.channel is not None else CHANNEL_SLUG_MANUAL,
            external_order_id=row.external_order_id,
            status=row.status,
            email=row.email,
            customer_id=row.customer_id,
            invoice_id=row.invoice_id,
            invoice_number=invoice_number,
            pick_id=row.pick_id,
            delivery_id=row.delivery_id,
            error_message=row.error_message,
            allocations=list(row.allocations or []),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
