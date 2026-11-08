"""Money helpers for supplier document lines. No database and no model calls."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

CENT = Decimal("0.01")
UNIT = Decimal("0.0001")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def money(value: Decimal, places: Decimal = CENT) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def as_decimal(value: object) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def dec_str(value: Optional[Decimal], places: Decimal = CENT) -> Optional[str]:
    if value is None:
        return None
    return str(money(value, places))


def net_unit_price(
    unit_price: Decimal,
    qty: Decimal,
    discount_percent: Optional[Decimal],
    discount_amount: Optional[Decimal],
) -> Decimal:
    """Unit price after a percent discount and an amount discount spread over qty."""
    price = unit_price
    if discount_percent is not None and discount_percent != 0:
        price = price * (ONE - (discount_percent / HUNDRED))
    if discount_amount is not None and discount_amount != 0 and qty != 0:
        price = price - (discount_amount / qty)
    return money(price, UNIT)


def extended(net_unit: Decimal, qty: Decimal) -> Decimal:
    return money(net_unit * qty, CENT)


def within_cent(left: Decimal, right: Decimal) -> bool:
    return abs(money(left) - money(right)) <= CENT


def whole_qty(qty: Decimal) -> Optional[int]:
    if qty <= 0:
        return None
    whole = qty.to_integral_value(rounding=ROUND_HALF_UP)
    if abs(qty - whole) > Decimal("0.0001"):
        return None
    as_int = int(whole)
    if as_int < 1:
        return None
    return as_int
