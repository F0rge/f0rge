from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.crud.payment import PaymentCRUD
from app.crud.pick import PickCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.pick import Pick, PickStatus
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.payment import Payment, PaymentDirection
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.schemas.invoice import InvoiceLineResponse
from app.schemas.till import TillSaleCreate, TillSaleLocationStock, TillSaleResponse
from app.services.sku_bom import whole_component_qty
from app.services.books_events import BooksEventService
from app.services.category_posting import CategoryPostingService
from app.services.customer_credit import CustomerCreditService
from app.services.payment_terms import compute_due_date
from app.services.stock_movements import StockMovementService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_INVENTORY,
    CODE_VAT,
    LedgerPostingService,
)
from app.services.stocktakes import StocktakeService
from app.services.till_kit_pick import (
    REASON_MISSING_PARTS,
    REASON_SPLIT_PICK,
    kit_pick_message,
)
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from app.exceptions import ForbiddenError, KitRequiresPickError
from app.permissions import TILL_DISCOUNT, USERS_MANAGE
from app.services.permissions import PermissionService
from app.services.books_periods import assert_date_postable
from app.services.pricing import resolve_unit_ex_vat
from app.services.vat import CENT, ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class TillOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.location_stock_crud = LocationStockCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.invoice_crud = TaxInvoiceCRUD(db)
        self.payment_crud = PaymentCRUD(db)
        self.customer_crud = CustomerCRUD(db)
        self.posting = LedgerPostingService(db)
        self.category_posting = CategoryPostingService(db)
        self.events = BooksEventService(db)
        self.credit = CustomerCreditService(db)
        self.stock_movements = StockMovementService(db)
        self.bom_crud = SkuBomLineCRUD(db)
        self.pick_crud = PickCRUD(db)

    async def create_sale(
        self, data: TillSaleCreate, user_id: Optional[uuid.UUID] = None
    ) -> TillSaleResponse:
        if user_id is not None and any(line.discount_percent > 0 for line in data.lines):
            allowed = await PermissionService(self.db).has_permission(user_id, TILL_DISCOUNT)
            if not allowed:
                raise ForbiddenError("Till discount permission required")

        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        team_settings = await TeamSettingsCRUD(self.db).get_or_create_for_team(team.id)
        max_discount = team_settings.max_till_discount_percent
        if max_discount is not None and user_id is not None:
            if any(line.discount_percent > max_discount for line in data.lines):
                can_override = await PermissionService(self.db).has_permission(
                    user_id, USERS_MANAGE
                )
                if not can_override:
                    raise ConflictError(f"Discount exceeds maximum allowed ({max_discount}%)")

        await StocktakeService(self.db).assert_location_unlocked(data.location_id)
        from app.crud.location import LocationCRUD

        location = await LocationCRUD(self.db).get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot sell from archived location")
        if location.type != LocationType.SHOWROOM:
            raise ConflictError("Till sales are only allowed at showroom locations")

        if data.customer_id is not None:
            customer = await self.customer_crud.get_by_id(data.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found")
        else:
            customer = await self._get_walk_in_customer()
        override_note = None
        if not self.credit.is_walk_in(customer):
            override_note = await self.credit.authorize_override(
                credit_override=data.credit_override,
                credit_override_reason=data.credit_override_reason,
                user_id=user_id,
            )
            await self.credit.assert_not_held(customer, credit_override=data.credit_override)
        sale_date = datetime.date.today()
        await assert_date_postable(self.db, sale_date)

        line_inputs: list[tuple] = []
        cogs_parts: list[tuple[str, Decimal, Decimal]] = []
        stock_decrements: list[tuple[uuid.UUID, int]] = []
        reserved: dict[uuid.UUID, int] = {}
        picks_to_link: list[Pick] = []
        kit_blocks: list[dict] = []
        used_pick_ids: set[uuid.UUID] = set()
        candidate_pick_ids: list[uuid.UUID] = []
        for candidate in [*data.pick_ids, data.pick_id]:
            if candidate is not None and candidate not in candidate_pick_ids:
                candidate_pick_ids.append(candidate)
        total_cogs = Decimal(0)

        for line in data.lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            base_unit = await resolve_unit_ex_vat(self.db, sku, customer)

            bom_lines = await self.bom_crud.list_by_parent(sku.id)
            if bom_lines:
                line_cogs, pick, block = await self._kit_line_cogs(
                    sku=sku,
                    line_qty=line.qty,
                    bom_lines=bom_lines,
                    location_id=data.location_id,
                    location_name=location.name,
                    pick_ids=candidate_pick_ids,
                    used_pick_ids=used_pick_ids,
                    reserved=reserved,
                    stock_decrements=stock_decrements,
                )
                if block is not None:
                    kit_blocks.append(block)
                    continue
                if pick is not None:
                    picks_to_link.append(pick)
            else:
                location_stock = await self.location_stock_crud.get_by_sku_and_location(
                    line.sku_id,
                    data.location_id,
                )
                available = (
                    location_stock.on_hand if location_stock is not None else 0
                ) - reserved.get(sku.id, 0)
                if location_stock is None or available < line.qty:
                    raise ConflictError(
                        f"Insufficient on-hand quantity for {sku.our_ref} at this location"
                    )
                if location_stock.unit_cost_zar is None:
                    raise ConflictError(f"No unit cost for {sku.our_ref} at this location")
                line_cogs = (location_stock.unit_cost_zar * line.qty).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                reserved[sku.id] = reserved.get(sku.id, 0) + line.qty
                stock_decrements.append((sku.id, line.qty))

            total_cogs += line_cogs
            cogs_code = await self.category_posting.cogs_code_for_sku(sku)
            cogs_parts.append((cogs_code, line_cogs, Decimal(0)))
            line_inputs.append((sku, line.qty, line.discount_percent, base_unit))

        if kit_blocks:
            raise KitRequiresPickError(kit_blocks)

        subtotal = Decimal(0)
        vat_total = Decimal(0)
        total_inc = Decimal(0)
        invoice_line_models: list[InvoiceLine] = []
        sales_parts: list[tuple[str, Decimal, Decimal]] = []

        for index, (sku, qty, discount_percent, base_unit) in enumerate(line_inputs):
            discounted_unit = (
                base_unit * (Decimal(100) - discount_percent) / Decimal(100)
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            ex_vat = (Decimal(qty) * discounted_unit).quantize(CENT, rounding=ROUND_HALF_UP)
            inc_vat = ex_to_inc(ex_vat)
            line_vat = inc_vat - ex_vat
            subtotal += ex_vat
            vat_total += line_vat
            total_inc += inc_vat
            sales_code = await self.category_posting.sales_code_for_sku(sku)
            sales_parts.append((sales_code, Decimal(0), ex_vat))
            invoice_line_models.append(
                InvoiceLine(
                    description=sku.name,
                    qty=qty,
                    unit_ex_vat=discounted_unit,
                    ex_vat=ex_vat,
                    inc_vat=inc_vat,
                    vat_amount=line_vat,
                    sort_order=index,
                    sku_id=sku.id,
                )
            )

        if subtotal <= 0:
            raise ValidationError("Sale total must be positive")

        if not self.credit.is_walk_in(customer):
            await self.credit.assert_within_limit(
                customer, total_inc, credit_override=data.credit_override
            )

        due_date = compute_due_date(sale_date, customer, team_settings)

        async with unit_of_work(self.db):
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
                lines=invoice_line_models,
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
                tender=data.tender,
            )

            await self.invoice_crud.add_and_flush(invoice)
            payment.invoice_id = invoice.id

            await self.posting.post(
                JournalDocumentType.INVOICE,
                invoice.id,
                f"Till tax invoice {invoice_number}",
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
            await self.posting.post(
                JournalDocumentType.PAYMENT,
                payment.id,
                f"Till payment {payment_number} ({data.tender})",
                [
                    (CODE_BANK, total_inc, Decimal(0)),
                    (CODE_AR, Decimal(0), total_inc),
                ],
                entry_date=sale_date,
            )

            if total_cogs > 0:
                await self.posting.post(
                    JournalDocumentType.INVOICE,
                    invoice.id,
                    f"COGS for till sale {invoice_number}",
                    self.category_posting.collapse(
                        [
                            *cogs_parts,
                            (CODE_INVENTORY, Decimal(0), total_cogs),
                        ]
                    ),
                    entry_date=sale_date,
                )

            for sku_id, qty in stock_decrements:
                await self.stock_movements.apply_bin_qty_delta(
                    sku_id=sku_id,
                    location_id=data.location_id,
                    qty_delta=-qty,
                )

            for pick in picks_to_link:
                pick.invoice_id = invoice.id

            invoice.amount_paid = total_inc
            await self.events.record(
                BooksDocumentType.INVOICE,
                invoice.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
                note=override_note,
            )
            await self.events.record(
                BooksDocumentType.PAYMENT,
                payment.id,
                BooksEventAction.CREATED,
                actor_user_id=user_id,
            )
            await self.invoice_crud.commit_refresh(invoice)

        if user_id is not None:
            from app.services.picks import PickService

            pick_service = PickService(self.db)
            for pick in picks_to_link:
                await pick_service.ensure_delivery(pick.id, user_id)

        reloaded = await self.invoice_crud.get_by_id(invoice.id)
        assert reloaded is not None

        remaining_stock = await self.location_stock_crud.get_by_sku_and_location(
            line_inputs[0][0].id,
            data.location_id,
        )
        on_hand = remaining_stock.on_hand if remaining_stock is not None else 0

        return TillSaleResponse(
            invoice_id=reloaded.id,
            invoice_number=reloaded.invoice_number,
            payment_id=payment.id,
            payment_number=payment.payment_number,
            tender=data.tender,
            issue_date=reloaded.issue_date,
            subtotal_ex_vat=reloaded.subtotal_ex_vat,
            vat_amount=reloaded.vat_amount,
            total_inc_vat=reloaded.total_inc_vat,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=line.ex_vat,
                    inc_vat=line.inc_vat,
                    vat_amount=line.vat_amount,
                    sort_order=line.sort_order,
                    sku_id=line.sku_id,
                )
                for line in reloaded.lines
            ],
            location=TillSaleLocationStock(
                location_id=location.id,
                location_name=location.name,
                on_hand=on_hand,
            ),
        )

    async def _matching_kit_pick(
        self,
        pick_ids: list[uuid.UUID],
        sku_id: uuid.UUID,
        line_qty: int,
        used_pick_ids: set[uuid.UUID],
    ) -> Optional[Pick]:
        invoiced_match = False
        for pick_id in pick_ids:
            if pick_id in used_pick_ids:
                continue
            pick = await self.pick_crud.get_by_id(pick_id)
            if (
                pick is None
                or pick.status not in (PickStatus.CONFIRMED, PickStatus.PICKING, PickStatus.STAGED)
                or pick.kit_sku_id != sku_id
                or pick.kit_qty != line_qty
            ):
                continue
            if pick.invoice_id is not None:
                invoiced_match = True
                continue
            used_pick_ids.add(pick_id)
            return pick
        if invoiced_match:
            raise ConflictError("Pick is already linked to an invoice")
        return None

    async def _component_on_hand_total(self, sku_id: uuid.UUID) -> int:
        rows = await self.location_stock_crud.list_by_sku_id(sku_id)
        total = 0
        for row in rows:
            location = row.location
            if location is not None and location.is_archived:
                continue
            total += row.on_hand
        return total

    async def _kit_block_reason(
        self,
        bom_lines,
        line_qty: int,
        reserved: dict[uuid.UUID, int],
    ) -> str:
        for bom in bom_lines:
            need = whole_component_qty(bom.qty, line_qty)
            available = await self._component_on_hand_total(bom.component_sku_id)
            available -= reserved.get(bom.component_sku_id, 0)
            if available < need:
                return REASON_MISSING_PARTS
        return REASON_SPLIT_PICK

    async def _kit_line_cogs(
        self,
        sku,
        line_qty: int,
        bom_lines,
        location_id: uuid.UUID,
        location_name: str,
        pick_ids: list[uuid.UUID],
        used_pick_ids: set[uuid.UUID],
        reserved: dict[uuid.UUID, int],
        stock_decrements: list[tuple[uuid.UUID, int]],
    ) -> tuple[Decimal, Optional[Pick], Optional[dict]]:
        showroom_ok = True
        for bom in bom_lines:
            need = whole_component_qty(bom.qty, line_qty)
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                bom.component_sku_id,
                location_id,
            )
            available = (loc_stock.on_hand if loc_stock is not None else 0) - reserved.get(
                bom.component_sku_id, 0
            )
            if loc_stock is None or available < need:
                showroom_ok = False
                break

        if showroom_ok:
            line_cogs = Decimal(0)
            for bom in bom_lines:
                need = whole_component_qty(bom.qty, line_qty)
                component = await self.sku_crud.get_by_id(bom.component_sku_id)
                if component is None:
                    raise NotFoundError("SKU not found")
                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    bom.component_sku_id,
                    location_id,
                )
                assert loc_stock is not None
                if loc_stock.unit_cost_zar is None:
                    raise ConflictError(f"No unit cost for {component.our_ref} at this location")
                line_cogs += (loc_stock.unit_cost_zar * need).quantize(
                    CENT,
                    rounding=ROUND_HALF_UP,
                )
                reserved[bom.component_sku_id] = reserved.get(bom.component_sku_id, 0) + need
                stock_decrements.append((bom.component_sku_id, need))
            return line_cogs, None, None

        pick = await self._matching_kit_pick(pick_ids, sku.id, line_qty, used_pick_ids)
        if pick is None:
            reason = await self._kit_block_reason(bom_lines, line_qty, reserved)
            return (
                Decimal(0),
                None,
                {
                    "sku_id": str(sku.id),
                    "sku_code": sku.our_ref,
                    "sku_name": sku.name,
                    "qty": line_qty,
                    "location_id": str(location_id),
                    "location_name": location_name,
                    "reason": reason,
                    "message": kit_pick_message(sku.name, sku.our_ref, location_name, reason),
                },
            )

        line_cogs = Decimal(0)
        for pick_line in pick.lines:
            component = await self.sku_crud.get_by_id(pick_line.sku_id)
            if component is None:
                raise NotFoundError("SKU not found")
            for alloc in pick_line.allocations:
                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    pick_line.sku_id,
                    alloc.location_id,
                )
                cost = loc_stock.unit_cost_zar if loc_stock is not None else None
                if cost is None:
                    showroom = await self.location_stock_crud.get_by_sku_and_location(
                        pick_line.sku_id,
                        location_id,
                    )
                    cost = showroom.unit_cost_zar if showroom is not None else None
                if cost is None:
                    raise ConflictError(f"No unit cost for {component.our_ref}")
                line_cogs += (cost * alloc.qty).quantize(CENT, rounding=ROUND_HALF_UP)
        return line_cogs, pick, None

    async def _get_walk_in_customer(self):
        from app.models.customer import Customer

        walk_in = (
            await self.db.execute(
                select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
            )
        ).scalar_one_or_none()
        if walk_in is None:
            raise NotFoundError("Walk-in customer not seeded")
        return walk_in
