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
from app.services.vat import CENT, ex_to_inc

# A Cin7 placeholder of R1.00 ex VAT, or R1.00 incl. VAT stored as R0.87 ex at 15%, is at
# or under this line. R1.01 ex is not.
PLACEHOLDER_UNIT_EX_VAT = Decimal("1.00")

RESTRICTED_SUSPECT_PRICE_WARNING = "Price looks wrong (R1 or below cost) – check with the owner"


class _PricedLine(Protocol):
    sku_id: Optional[uuid.UUID]
    unit_ex_vat: Decimal
    suspect_price_warning: Optional[str]


def cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def is_placeholder_unit(unit_ex_vat: Decimal) -> bool:
    """True when the ex-VAT unit is R1.00 or less."""
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


def _unit_phrase(unit_ex_vat: Decimal, *, inclusive_vat_rate: Optional[Decimal]) -> str:
    """Quote the unit in the basis the line shows. Cost stays ex VAT elsewhere."""
    if inclusive_vat_rate is not None:
        inc = ex_to_inc(unit_ex_vat, inclusive_vat_rate)
        return f"R{inc:.2f} incl. VAT (R{unit_ex_vat:.2f} excl.)"
    return f"R{unit_ex_vat:.2f} excl. VAT"


def suspect_unit_price_warning(
    unit_ex_vat: Decimal,
    average_cost: Optional[Decimal],
    *,
    reveal_cost: bool,
    inclusive_vat_rate: Optional[Decimal] = None,
) -> Optional[str]:
    """Staff warning for one unit price. ``reveal_cost`` is ``stock.cost.view``.

    Detection uses the ex-VAT unit. ``inclusive_vat_rate`` (the document's rate, set for
    a Retail line) only changes the wording to quote the unit incl. VAT as well.
    """
    unit = cents(unit_ex_vat)
    placeholder = unit <= PLACEHOLDER_UNIT_EX_VAT
    cost = cents(average_cost) if average_cost is not None else None
    below_cost = cost is not None and unit < cost
    if not placeholder and not below_cost:
        return None
    if not reveal_cost:
        return RESTRICTED_SUSPECT_PRICE_WARNING
    shown = _unit_phrase(unit, inclusive_vat_rate=inclusive_vat_rate)
    if placeholder and below_cost and cost is not None:
        return (
            f"Unit price {shown} is R1.00 excl. VAT or below and below "
            f"average cost R{cost:.2f} excl. VAT."
        )
    if below_cost and cost is not None:
        return f"Unit price {shown} is below average cost R{cost:.2f} excl. VAT."
    return f"Unit price {shown} is R1.00 excl. VAT or below. Check this price."


def suspect_line_warning(
    unit_ex_vat: Decimal,
    discount_percent: Optional[Decimal],
    average_cost: Optional[Decimal],
    *,
    reveal_cost: bool,
    inclusive_vat_rate: Optional[Decimal] = None,
) -> Optional[str]:
    """Warning for a sale line. ``reveal_cost`` is ``stock.cost.view``.

    Cost viewers are warned on the net unit after the line discount, so a discount that
    takes the line below cost is flagged. Anyone else is warned on the unit before the
    discount only: a discount they may give must not let them probe the average cost.
    A None discount is a stored line whose unit is already net.
    """
    unit = unit_ex_vat
    if reveal_cost and discount_percent:
        unit = cents(unit * (Decimal(100) - discount_percent) / Decimal(100))
    return suspect_unit_price_warning(
        unit, average_cost, reveal_cost=reveal_cost, inclusive_vat_rate=inclusive_vat_rate
    )


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
    inclusive_vat_rate: Optional[Decimal],
) -> None:
    """Fill ``suspect_price_warning`` from the stored unit. Does not write the row."""
    sku_ids = [line.sku_id for line in lines if line.sku_id is not None]
    costs = await average_costs_by_sku_id(db, sku_ids)
    reveal_cost = await viewer_can_see_cost(db, viewer_user_id)
    for line in lines:
        cost = costs.get(line.sku_id) if line.sku_id is not None else None
        line.suspect_price_warning = suspect_line_warning(
            line.unit_ex_vat,
            getattr(line, "discount_percent", None),
            cost,
            reveal_cost=reveal_cost,
            inclusive_vat_rate=inclusive_vat_rate,
        )
