from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class HomeSummaryResponse(BaseModel):
    on_order_qty: int
    on_order_value_zar: Decimal
    on_hand_qty: int
    on_hand_value_zar: Decimal
    home_currency: str
