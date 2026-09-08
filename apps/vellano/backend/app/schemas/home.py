from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class HomeAttentionItem(BaseModel):
    kind: str
    title: str
    detail: str
    status: str
    href: str


class HomeRecentMovement(BaseModel):
    source: str
    title: str
    detail: str
    created_at: datetime.datetime


class HomeSummaryResponse(BaseModel):
    on_order_qty: int
    on_order_value_zar: Decimal
    on_hand_qty: int
    on_hand_value_zar: Decimal
    home_currency: str
    aged_stock_value_zar: Decimal
    open_laybys_count: int
    open_laybys_balance_zar: Decimal
    low_stock_count: int
    open_returns_count: int
    needs_attention: list[HomeAttentionItem]
    recent_movements: list[HomeRecentMovement]
