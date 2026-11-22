from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from f0rge_core.exceptions import ValidationError

VAT_MULTIPLIER = Decimal("1.15")
CENT = Decimal("0.01")


def ex_to_inc(ex: Decimal) -> Decimal:
    return (ex * VAT_MULTIPLIER).quantize(CENT, rounding=ROUND_HALF_UP)


def inc_to_ex(inc: Decimal) -> Decimal:
    return (inc / VAT_MULTIPLIER).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_non_negative_price(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValidationError(f"{field_name} must not be negative")


def inc_vat_or_none(ex_vat: Optional[Decimal]) -> Optional[Decimal]:
    if ex_vat is None:
        return None
    return ex_to_inc(ex_vat)
