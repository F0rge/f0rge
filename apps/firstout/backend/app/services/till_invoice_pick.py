"""Till sales of stock held outside the till's showroom (spec #979, ticket #986).

The sale deducts only what the showroom has. The rest stays reserved against the tax
invoice, with no expiry, and a draft till pick carries it. Confirming that pick deducts
the stock at its sources and books the cost of sales there.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.purchase_order import LocationStockCRUD
from app.crud.stock_reservation import StockReservationCRUD
from app.models.journal import JournalDocumentType
from app.models.pick import Pick, PickSourceType, PickStatus
from app.models.stock_reservation import HOLDER_INVOICE, StockReservation
from app.models.unit_cost_audit import UnitCostAuditSource
from app.services.books_periods import assert_date_postable
from app.services.category_posting import CategoryPostingService
from app.services.chart_of_accounts import CODE_INVENTORY, LedgerPostingService
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.vat import CENT
from f0rge_core.exceptions import ConflictError


def is_invoice_reserved(pick: Pick) -> bool:
    """A till pick linked to its invoice with no kit: its stock is reserved, not yet deducted."""
    return (
        pick.source_type == PickSourceType.TILL
        and pick.invoice_id is not None
        and pick.kit_sku_id is None
    )


class TillInvoicePick:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def assert_picks_confirmed(self, invoice_id: uuid.UUID, invoice_number: str) -> None:
        """A return needs the invoice's off-site stock deducted first, or it would credit stock never taken."""
        unconfirmed = await self.db.scalar(
            select(Pick.id)
            .where(
                Pick.invoice_id == invoice_id,
                Pick.source_type == PickSourceType.TILL,
                Pick.kit_sku_id.is_(None),
                Pick.status == PickStatus.DRAFT,
            )
            .limit(1)
        )
        if unconfirmed is not None:
            raise ConflictError(
                f"Confirm the pick list for {invoice_number} before processing a return."
            )

    def reserve(
        self, invoice_id: uuid.UUID, location_id: uuid.UUID, remainders: dict[uuid.UUID, int]
    ) -> None:
        """Stage the invoice's reservations; they never expire."""
        for sku_id, qty in remainders.items():
            self.db.add(
                StockReservation(
                    sku_id=sku_id,
                    qty=qty,
                    holder_kind=HOLDER_INVOICE,
                    holder_id=invoice_id,
                    location_id=location_id,
                    expires_at=None,
                )
            )

    async def deduct(self, pick: Pick, user_id: uuid.UUID) -> None:
        """Deduct every allocation at its source with COGS there, then release the reservations.

        Every source is checked before anything is posted, so a short source changes nothing.
        """
        assert pick.invoice is not None
        today = datetime.date.today()
        await assert_date_postable(self.db, today)
        stocks = LocationStockCRUD(self.db)
        category_posting = CategoryPostingService(self.db)
        movements: list[tuple[uuid.UUID, uuid.UUID, int]] = []
        cogs_parts: list[tuple[str, Decimal, Decimal]] = []
        total_cogs = Decimal(0)
        consumed: dict[uuid.UUID, int] = {}
        for line in pick.lines:
            for alloc in line.allocations:
                await StocktakeService(self.db).assert_location_unlocked(alloc.location_id)
                where = f"{line.sku.our_ref} at {alloc.location.name}"
                stock = await stocks.get_by_sku_and_location(line.sku_id, alloc.location_id)
                if stock is None or stock.on_hand < alloc.qty:
                    raise ConflictError(f"Insufficient stock for {where}")
                if stock.unit_cost_zar is None:
                    raise ConflictError(f"No unit cost for {where}")
                cogs = (stock.unit_cost_zar * alloc.qty).quantize(CENT, rounding=ROUND_HALF_UP)
                total_cogs += cogs
                cogs_parts.append((await category_posting.cogs_code_for_sku(line.sku), cogs, 0))
                movements.append((line.sku_id, alloc.location_id, alloc.qty))
                consumed[line.sku_id] = consumed.get(line.sku_id, 0) + alloc.qty

        if total_cogs > 0:
            await LedgerPostingService(self.db).post(
                JournalDocumentType.INVOICE,
                pick.invoice_id,
                f"COGS for till pick {pick.number} ({pick.invoice.invoice_number})",
                category_posting.collapse([*cogs_parts, (CODE_INVENTORY, Decimal(0), total_cogs)]),
                entry_date=today,
            )
        for sku_id, location_id, qty in movements:
            await StockMovementService(self.db).apply_outgoing_qty(
                sku_id=sku_id,
                location_id=location_id,
                qty=qty,
                user_id=user_id,
                source=UnitCostAuditSource.TILL_PICK,
                note=f"Till pick {pick.number} confirm",
            )

        held = await StockReservationCRUD(self.db).held_by((HOLDER_INVOICE, pick.invoice_id))
        for sku_id, qty in consumed.items():
            row = held.get(sku_id)
            if row is None:
                continue
            if row.qty > qty:
                row.qty -= qty
            else:
                await self.db.delete(row)
