"""Exact stock quantities in Python; JSON numbers retain existing client contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import Field, PlainSerializer


def quantity_text(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


Quantity = Annotated[
    Decimal,
    Field(max_digits=14, decimal_places=4, allow_inf_nan=False),
    PlainSerializer(float, return_type=float, when_used="json"),
]

# Totals can exceed one stored cell's Numeric(14,4) range. Keep calculation
# precision in Decimal without imposing the per-cell bound on report responses.
QuantityTotal = Annotated[
    Decimal,
    Field(decimal_places=4, allow_inf_nan=False),
    PlainSerializer(float, return_type=float, when_used="json"),
]
