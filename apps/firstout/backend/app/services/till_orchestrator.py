from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.customer import CustomerCRUD
from app.services.sales_staff import SalesStaffService
from app.services.party_archive import assert_customer_active
from app.services.sellability import assert_sku_sellable
from app.services.sku_archive import SkuArchiveService
from app.services.quantities import whole_available_quantity
from app.crud.payment import PaymentCRUD
from app.crud.pick import PickCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.sku_bom_line import SkuBomLineCRUD
from app.crud.tax_invoice import TaxInvoiceCRUD
from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.models.pick import Pick, PickSourceType, PickStatus
from app.models.books_event import BooksDocumentType, BooksEventAction
from app.models.journal import JournalDocumentType
from app.models.location import LocationType
from app.models.payment import Payment, PaymentDirection
from app.models.quote import QuoteStatus
from app.models.customer import Customer
from app.models.sku import Sku
from app.models.tax_invoice import InvoiceLine
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.invoice import InvoiceLineResponse
from app.schemas.till import (
    TillPriceLine,
    TillPricePreview,
    TillPriceRequest,
    TillSaleCreate,
    TillSaleLocationStock,
    TillSaleResponse,
)
from app.services.sku_bom import whole_component_qty
from app.services.books_events import BooksEventService
from app.services.category_posting import CategoryPostingService
from app.services.customer_credit import CustomerCreditService
from app.services.stock_movements import StockMovementService
from app.services.chart_of_accounts import (
    CODE_AR,
    CODE_BANK,
    CODE_INVENTORY,
    LedgerPostingService,
)
from app.services.stocktakes import StocktakeService
from app.services.till_invoice_pick import TillInvoicePick
from app.services.till_kit_pick import (
    REASON_MISSING_PARTS,
    REASON_SPLIT_PICK,
    kit_pick_message,
)
from app.services.till_seed import WALK_IN_CUSTOMER_NAME
from app.exceptions import (
    BasketExpiredSignal,
    ForbiddenError,
    KitRequiresPickError,
    TillPriceConflictError,
)
from app.permissions import TILL_DISCOUNT, USERS_MANAGE
from app.services.permissions import PermissionService
from app.services.till_pricing import TillPricing
from app.services.tax_invoice_issue import TaxInvoiceIssue
from app.services.suspect_price import annotate_line_warnings
from app.services.vat import CENT
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

    async def require_discounts(
        self, request: TillPriceRequest, user_id: uuid.UUID | None, max_discount: Decimal | None
    ) -> None:
        """Line discounts need till.discount; above the team maximum, users.manage too."""
        if user_id is None or not any(line.discount_percent > 0 for line in request.lines):
            return
        permissions = PermissionService(self.db)
        if not await permissions.has_permission(user_id, TILL_DISCOUNT):
            raise ForbiddenError("Till discount permission required")
        if max_discount is not None and any(
            line.discount_percent > max_discount for line in request.lines
        ):
            if not await permissions.has_permission(user_id, USERS_MANAGE):
                raise ConflictError(f"Discount exceeds maximum allowed ({max_discount}%)")

    async def _active_customer(self, request: TillPriceRequest) -> Customer:
        if request.customer_id is None:
            customer = await self._get_walk_in_customer()
        else:
            customer = await self.customer_crud.get_by_id(request.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found")
        assert_customer_active(customer)
        return customer

    async def _price_cart(
        self, request: TillPriceRequest, customer: Customer
    ) -> tuple[list[Sku], TillPricePreview]:
        pricing = await TillPricing.for_customer(self.db, customer)
        skus = []
        priced_lines = []
        for line in request.lines:
            sku = await self.sku_crud.get_by_id(line.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            if sku.is_sellable is False:
                assert_sku_sellable(sku)
            skus.append(sku)
            priced_lines.append(await pricing.line(sku, line))
        return skus, pricing.preview(priced_lines)

    async def preview_prices(
        self, request: TillPriceRequest, user_id: uuid.UUID
    ) -> TillPricePreview:
        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        settings = await TeamSettingsCRUD(self.db).get_by_team_id(team.id)
        await self.require_discounts(
            request, user_id, settings.max_till_discount_percent if settings else None
        )
        customer = await self._active_customer(request)
        _, preview = await self._price_cart(request, customer)
        return preview

    async def create_sale(
        self, data: TillSaleCreate, user_id: Optional[uuid.UUID] = None
    ) -> TillSaleResponse:
        # Taken before any lock wait: a request that started before expiry completes.
        started = datetime.datetime.now(datetime.timezone.utc)
        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        settings_crud = TeamSettingsCRUD(self.db)
        settings = await settings_crud.get_by_team_id(team.id)
        await self.require_discounts(
            data, user_id, settings.max_till_discount_percent if settings else None
        )

        await StocktakeService(self.db).assert_location_unlocked(data.location_id)
        from app.crud.location import LocationCRUD

        location = await LocationCRUD(self.db).get_by_id(data.location_id)
        if location is None:
            raise NotFoundError("Location not found")
        if location.is_archived:
            raise ConflictError("Cannot sell from archived location")
        if location.type != LocationType.SHOWROOM:
            raise ConflictError("Till sales are only allowed at showroom locations")
        await SalesStaffService(self.db).check_sale_colleague(data.sales_staff_id)
        quote = None
        quote_number: Optional[str] = None
        if data.quote_id is not None:
            from app.services.quotes import QuotesService

            # Locked until the sale commits: a quote converts into exactly one invoice.
            quote = await QuotesService(self.db).lock_for_conversion(data.quote_id)
            quote_number = quote.quote_number

        from app.services.till_basket import TillBasketService

        baskets = TillBasketService(self.db)
        basket = None
        if data.basket_id is not None:
            if user_id is None:
                raise ValidationError("A basket sale needs a signed-in user")
            # An expired basket is emptied and refused here, before anything posts.
            try:
                basket = await baskets.lock_live(data.basket_id, user_id, data.location_id, started)
            except BasketExpiredSignal as expired:
                await baskets.refuse_expired(expired)
                raise
            baskets.assert_matches(basket, data.lines, data.basket_version)
            await baskets.prune(started)

        customer = await self._active_customer(data)
        on_account = data.tender == "statement"
        # Pay on statement takes any customer: no credit hold or limit checks.
        credit_checked = not on_account and not self.credit.is_walk_in(customer)
        override_note = None
        if credit_checked:
            override_note = await self.credit.authorize_override(
                credit_override=data.credit_override,
                credit_override_reason=data.credit_override_reason,
                user_id=user_id,
            )
            await self.credit.assert_not_held(customer, credit_override=data.credit_override)
        sale_date = datetime.date.today()
        if data.due_date is not None and data.due_date < sale_date:
            raise ValidationError("Due date cannot be before the issue date")

        line_inputs: list[tuple[Sku, TillPriceLine]] = []
        # Lines that book cost of goods: (line index, SKU, cost a pick already moved,
        # stock this sale takes off the showroom shelf as (sku_id, qty, our_ref)).
        costed: list[tuple[int, Sku, Decimal, list[tuple[uuid.UUID, int, str]]]] = []
        non_stock_service_sku_ids: set[uuid.UUID] = set()
        reserved: dict[uuid.UUID, int] = {}
        remainders: dict[uuid.UUID, int] = {}
        picks_to_link: list[Pick] = []
        kit_blocks: list[dict] = []
        used_pick_ids: set[uuid.UUID] = set()
        candidate_pick_ids: list[uuid.UUID] = []
        for candidate in [*data.pick_ids, data.pick_id]:
            if candidate is not None and candidate not in candidate_pick_ids:
                candidate_pick_ids.append(candidate)
        pick_id: Optional[uuid.UUID] = None

        await SkuArchiveService(self.db).lock_skus([line.sku_id for line in data.lines])
        skus, preview = await self._price_cart(data, customer)
        if data.price_revision is not None and data.price_revision != preview.price_revision:
            raise TillPriceConflictError(
                "Prices changed. Review the new total before completing the sale."
            )
        for sku, line in zip(skus, preview.lines, strict=True):
            existing_pick = None
            if sku.is_sellable is False:
                assert_sku_sellable(sku)
            if sku.is_archived:
                existing_pick = await self._existing_archived_pick(
                    candidate_pick_ids, sku, line.qty, customer.id, used_pick_ids
                )
            else:
                assert_sku_sellable(sku)
            bom_lines = await self.bom_crud.list_by_parent(sku.id)
            if sku.till_no_stock_required and existing_pick is None and not bom_lines:
                non_stock_service_sku_ids.add(sku.id)
                line_inputs.append((sku, line))
                continue
            line_cogs = Decimal(0)
            decrements: list[tuple[uuid.UUID, int, str]] = []
            if existing_pick is not None:
                line_cogs = await self._pick_cogs(existing_pick, data.location_id)
                picks_to_link.append(existing_pick)
            elif bom_lines:
                line_cogs, pick, block = await self._kit_line_cogs(
                    sku=sku,
                    line_qty=line.qty,
                    bom_lines=bom_lines,
                    location_id=data.location_id,
                    location_name=location.name,
                    pick_ids=candidate_pick_ids,
                    used_pick_ids=used_pick_ids,
                    reserved=reserved,
                    stock_decrements=decrements,
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
                here = line.qty
                if available < line.qty:
                    if basket is None:
                        raise ConflictError(
                            f"Insufficient on-hand quantity for {sku.our_ref} at this location"
                        )
                    # Sold from the basket: this showroom gives what it has, the rest is
                    # reserved for the invoice and picked from elsewhere.
                    here = min(line.qty, whole_available_quantity(max(available, 0)))
                    remainders[sku.id] = remainders.get(sku.id, 0) + line.qty - here
                if here > 0:
                    reserved[sku.id] = reserved.get(sku.id, 0) + here
                    decrements.append((sku.id, here, sku.our_ref))
                else:
                    # Nothing here: the line books no cost of sales until its pick is confirmed.
                    line_inputs.append((sku, line))
                    continue

            costed.append((len(line_inputs), sku, line_cogs, decrements))
            line_inputs.append((sku, line))

        if kit_blocks:
            raise KitRequiresPickError(kit_blocks)

        subtotal = preview.subtotal_ex_vat
        total_inc = preview.total_inc_vat
        invoice_line_models: list[InvoiceLine] = []

        for index, (sku, line) in enumerate(line_inputs):
            discounted_unit = (line.ex_vat / line.qty).quantize(CENT, rounding=ROUND_HALF_UP)
            invoice_line_models.append(
                InvoiceLine(
                    description=sku.name,
                    qty=line.qty,
                    unit_ex_vat=discounted_unit,
                    ex_vat=line.ex_vat,
                    inc_vat=line.inc_vat,
                    vat_amount=line.vat_amount,
                    sort_order=index,
                    sku_id=sku.id,
                    price_warning=line.price_warning,
                    till_no_stock_required=sku.id in non_stock_service_sku_ids,
                )
            )

        if subtotal <= 0:
            raise ValidationError("Sale total must be positive")

        if credit_checked:
            await self.credit.assert_within_limit(
                customer, total_inc, credit_override=data.credit_override
            )

        async with unit_of_work(self.db):
            invoice = await TaxInvoiceIssue(self.db).issue(
                customer=customer,
                issue_date=sale_date,
                due_date=data.due_date,
                lines=invoice_line_models,
                prices_include_vat=preview.prices_include_vat,
                memo="Till tax invoice",
                actor_user_id=user_id,
                event_note=override_note,
                sales_staff_id=data.sales_staff_id,
                on_account=on_account,
                note_printed=data.note_printed,
                note_internal=data.note_internal,
                source="till",
            )
            invoice_number = invoice.invoice_number

            payment: Optional[Payment] = None
            if not on_account:
                payment = Payment(
                    payment_number=await self.payment_crud.get_next_payment_number(),
                    direction=PaymentDirection.IN,
                    invoice_id=invoice.id,
                    amount=total_inc,
                    currency="ZAR",
                    fx_to_zar=Decimal("1"),
                    amount_zar=total_inc,
                    fx_gain_loss_zar=Decimal(0),
                    paid_on=sale_date,
                    tender=data.tender,
                )
                await self.payment_crud.add_and_flush(payment)
                await self.posting.post(
                    JournalDocumentType.PAYMENT,
                    payment.id,
                    f"Till payment {payment.payment_number} ({data.tender})",
                    [
                        (CODE_BANK, total_inc, Decimal(0)),
                        (CODE_AR, Decimal(0), total_inc),
                    ],
                    entry_date=sale_date,
                )

            # Stock leaves in the same order as before (row-lock order); cost of goods is what
            # each movement consumed, read from its locked row.
            total_cogs = Decimal(0)
            cogs_parts: list[tuple[str, Decimal, Decimal]] = []
            for index, sku, line_cogs, decrements in costed:
                for sku_id, qty, our_ref in decrements:
                    taken = await self.stock_movements.apply_outgoing_qty(
                        sku_id=sku_id,
                        location_id=data.location_id,
                        qty=Decimal(qty),
                        user_id=user_id,
                        source=UnitCostAuditSource.TILL,
                        note=f"Till sale {invoice_number}",
                        # ponytail: the till audit row is deferred one release, so the image a
                        # failed release rolls back to already reads "till" before anything
                        # writes it (an unknown enum value 500s Home and cost audit). The
                        # follow-up release flips this to True.
                        record_audit=False,
                    )
                    if taken.unit_cost_zar is None:
                        raise ConflictError(f"No unit cost for {our_ref} at this location")
                    line_cogs += taken.total_zar
                    invoice_line = invoice_line_models[index]
                    if sku_id == invoice_line.sku_id and qty == invoice_line.qty:
                        # The whole line left this shelf: a return restocks it at this cost.
                        invoice_line.unit_cost_zar = taken.unit_cost_zar
                total_cogs += line_cogs
                cogs_parts.append(
                    (await self.category_posting.cogs_code_for_sku(sku), line_cogs, Decimal(0))
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

            for pick in picks_to_link:
                pick.invoice_id = invoice.id

            if quote is not None:
                quote.status = QuoteStatus.CONVERTED
                quote.converted_invoice_id = invoice.id

            if payment is not None:
                invoice.amount_paid = total_inc
            if basket is not None:
                # Releases the basket's reservations in the transaction that deducts stock.
                await baskets.set_contents(basket)
            if remainders:
                # Same transaction: the units are never unreserved, and the pick exists with them.
                assert user_id is not None
                TillInvoicePick(self.db).reserve(invoice.id, data.location_id, remainders)
                from app.services.picks import PickService

                till_pick = await PickService(self.db).stage_till_invoice_pick(
                    invoice.id, customer.id, remainders, user_id
                )
                pick_id = till_pick.id
            if payment is not None:
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

        sale = TillSaleResponse(
            invoice_id=reloaded.id,
            pick_id=pick_id,
            invoice_number=reloaded.invoice_number,
            payment_id=payment.id if payment is not None else None,
            payment_number=payment.payment_number if payment is not None else None,
            tender=data.tender,
            issue_date=reloaded.issue_date,
            due_date=reloaded.due_date,
            on_account=reloaded.on_account,
            quote_number=quote_number,
            subtotal_ex_vat=reloaded.subtotal_ex_vat,
            vat_amount=reloaded.vat_amount.quantize(CENT),
            total_inc_vat=reloaded.total_inc_vat.quantize(CENT),
            prices_include_vat=reloaded.prices_include_vat,
            lines=[
                InvoiceLineResponse(
                    id=line.id,
                    description=line.description,
                    qty=line.qty,
                    unit_ex_vat=line.unit_ex_vat,
                    ex_vat=line.ex_vat,
                    inc_vat=line.inc_vat.quantize(CENT),
                    vat_amount=line.vat_amount.quantize(CENT),
                    sort_order=line.sort_order,
                    sku_id=line.sku_id,
                    price_warning=line.price_warning,
                    till_no_stock_required=line.till_no_stock_required,
                )
                for line in reloaded.lines
            ],
            location=TillSaleLocationStock(
                location_id=location.id,
                location_name=location.name,
                on_hand=on_hand,
            ),
        )
        await annotate_line_warnings(
            self.db,
            sale.lines,
            viewer_user_id=user_id,
            prices_include_vat=reloaded.prices_include_vat,
        )
        return sale

    async def _existing_archived_pick(
        self,
        pick_ids,
        sku,
        qty,
        customer_id,
        used_pick_ids,
    ) -> Pick:
        """Finish an exact pre-archive commitment; never mint another archived sale."""
        if sku.archived_at is None:
            raise ValidationError(f"Restore SKU {sku.our_ref} before adding it to new business")
        for pick_id in sorted(pick_ids, key=str):
            if pick_id in used_pick_ids:
                continue
            # The lifecycle team lock serializes till sales; the pick row lock also
            # protects against an existing pick cancellation during this handoff.
            pick = await self.pick_crud.get_by_id(pick_id, for_update=True)
            if (
                pick is None
                or pick.source_type != PickSourceType.TILL
                or pick.kit_sku_id != sku.id
                or pick.kit_qty != qty
                or pick.invoice_id is not None
                or pick.status not in (PickStatus.CONFIRMED, PickStatus.PICKING, PickStatus.STAGED)
                or pick.created_at > sku.archived_at
                or (pick.customer_id is not None and pick.customer_id != customer_id)
            ):
                continue
            used_pick_ids.add(pick.id)
            return pick
        raise ValidationError(
            f"Restore SKU {sku.our_ref} before adding it to new business; "
            "only its exact, unconsumed pre-archive pick can be completed"
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
            total += whole_available_quantity(row.on_hand)
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
        stock_decrements: list[tuple[uuid.UUID, int, str]],
    ) -> tuple[Decimal, Optional[Pick], Optional[dict]]:
        """Plan a kit line: its components leave the showroom (costed when they move, so the
        cost returned is 0), or a matching pick already moved them (cost returned), or a block."""
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
            for bom in bom_lines:
                need = whole_component_qty(bom.qty, line_qty)
                component = await self.sku_crud.get_by_id(bom.component_sku_id)
                if component is None:
                    raise NotFoundError("SKU not found")
                reserved[bom.component_sku_id] = reserved.get(bom.component_sku_id, 0) + need
                stock_decrements.append((bom.component_sku_id, need, component.our_ref))
            return Decimal(0), None, None

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

        return await self._pick_cogs(pick, location_id), pick, None

    async def _pick_cogs(self, pick: Pick, location_id: uuid.UUID) -> Decimal:
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
        return line_cogs

    async def _get_walk_in_customer(self) -> Customer:
        walk_in = (
            await self.db.execute(
                select(Customer).where(Customer.name == WALK_IN_CUSTOMER_NAME).limit(1)
            )
        ).scalar_one_or_none()
        if walk_in is None:
            raise NotFoundError("Walk-in customer not seeded")
        return walk_in
