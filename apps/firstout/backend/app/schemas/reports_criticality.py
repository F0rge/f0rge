from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class SkuCriticalityLine(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    category: Optional[str]
    qty: int
    value_zar: Decimal
    share_pct: Decimal
    cumulative_pct: Decimal
    abc_class: str
    hits_50pct_band: bool
    is_a: bool


class SkuCriticalityCategoryLine(BaseModel):
    category: str
    qty: int
    value_zar: Decimal
    share_pct: Decimal
    cumulative_pct: Decimal
    abc_class: str


class SkuCriticalityReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    sku_count_for_50pct: int
    sku_count_for_80pct: int
    top_sku_share_pct: Decimal
    lines: list[SkuCriticalityLine]
    categories: list[SkuCriticalityCategoryLine]
