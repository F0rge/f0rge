"""Warn when a document line's unit price looks like a placeholder or is below cost.

The check never changes the price and never blocks the document. Cost figures are
included only for callers who have ``stock.cost.view``.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.purchase_order import LocationStockCRUD
from app.permissions import STOCK_COST_VIEW
from app.services.packing_sheet import sku_level_unit_cost
from app.services.permissions import PermissionService
from app.services.vat import CENT

# R1.00 ex VAT is R1.15 incl. VAT. A Cin7 placeholder of R1.00 ex, or R1.00 incl.
# VAT stored as R0.87 ex, is at or under this line. R1.01 ex (R1.16 incl.) is not.
PLACEHOLDER_UNIT_EX_VAT = Decimal("1.00")

RESTRICTED_SUSPECT_PRICE_WARNING = "Price looks wrong (R1 or below cost) – check with the owner"


class _PricedLine(Protocol):
    sku_id: Optional[uuid.UUID]
    unit_ex_vat: Decimal
    suspect_price_warning: Optional[str]


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def is_placeholder_unit(unit_ex_vat: Decimal) -> bool:
    """True when the ex-VAT unit is R1.00 or less (R1.15 incl. VAT or less)."""
    return cents(unit_ex_vat) <= PLACEHOLDER_UNIT_EX_VAT


def is_below_average_cost(unit_ex_vat: Decimal, average_cost: Optional[Decimal]) -> bool:
    """True when the ex-VAT unit is strictly under the on-hand average cost."""
    if average_cost is None:
        return False
    return cents(unit_ex_vat) < cents(average_cost)


def tier_price_below_cost(amount: Optional[Decimal], average_cost: Optional[Decimal]) -> bool:
    """Catalogue tier flag. Blank and zero prices are missing, not below cost."""
    if amount is None or amount <= 0:
        return False
    return is_below_average_cost(amount, average_cost)


def suspect_unit_price_warning(
    unit_ex_vat: Decimal,
    average_cost: Optional[Decimal],
    *,
    reveal_cost: bool,
) -> Optional[str]:
    """Staff warning for one unit price. ``reveal_cost`` is ``stock.cost.view``."""
    unit = cents(unit_ex_vat)
    placeholder = unit <= PLACEHOLDER_UNIT_EX_VAT
    cost = cents(average_cost) if average_cost is not None else None
    below_cost = cost is not None and unit < cost
    if not placeholder and not below_cost:
        return None
    if not reveal_cost:
        return RESTRICTED_SUSPECT_PRICE_WARNING
    if placeholder and below_cost and cost is not None:
        return f"Unit price R{unit:.2f} is R1.00 or below and below average cost R{cost:.2f}."
    if below_cost and cost is not None:
        return f"Unit price R{unit:.2f} is below average cost R{cost:.2f}."
    return "Unit price is R1.00 or below (R1.15 incl. VAT or less). Check this price."


async def average_costs_by_sku_id(
    db: AsyncSession,
    sku_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Optional[Decimal]]:
    """Weighted average of location on-hand cost. None when nothing is on hand."""
    unique = list(dict.fromkeys(sku_ids))
    if not unique:
        return {}
    pairs = await LocationStockCRUD(db).on_hand_cost_pairs(unique)
    return {sku_id: sku_level_unit_cost(pairs.get(sku_id, [])) for sku_id in unique}


async def viewer_can_see_cost(db: AsyncSession, user_id: Optional[uuid.UUID]) -> bool:
    if user_id is None:
        return False
    return await PermissionService(db).has_permission(user_id, STOCK_COST_VIEW)


async def annotate_line_warnings(
    db: AsyncSession,
    lines: list[_PricedLine],
    *,
    viewer_user_id: Optional[uuid.UUID],
) -> None:
    """Fill ``suspect_price_warning`` from the stored unit. Does not write the row."""
    sku_ids = [line.sku_id for line in lines if line.sku_id is not None]
    costs = await average_costs_by_sku_id(db, sku_ids)
    reveal_cost = await viewer_can_see_cost(db, viewer_user_id)
    for line in lines:
        cost = costs.get(line.sku_id) if line.sku_id is not None else None
        line.suspect_price_warning = suspect_unit_price_warning(
            line.unit_ex_vat,
            cost,
            reveal_cost=reveal_cost,
        )
