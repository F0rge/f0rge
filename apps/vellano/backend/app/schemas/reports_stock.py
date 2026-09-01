from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class StockValuationLine(BaseModel):
    location_id: uuid.UUID
    location_name: str
    sku_id: uuid.UUID
    our_ref: str
    name: str
    on_hand: int
    unit_cost_zar: Optional[Decimal]
    value_zar: Decimal


class StockValuationReport(BaseModel):
    lines: list[StockValuationLine]
    total_on_hand: int
    total_value_zar: Decimal


class AgedStockLine(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    location_id: uuid.UUID
    location_name: str
    on_hand: int
    value_zar: Decimal
    days: int
    bucket: str


class AgedStockBucket(BaseModel):
    bucket: str
    label: str
    qty: int
    value_zar: Decimal
    lines: list[AgedStockLine]


class AgedStockReport(BaseModel):
    buckets: list[AgedStockBucket]
    total_qty: int
    total_value_zar: Decimal


class SalesBySkuLine(BaseModel):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: int
    ex_vat_zar: Decimal
    inc_vat_zar: Decimal


class SalesBySkuReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    lines: list[SalesBySkuLine]
    total_qty: int
    total_ex_vat_zar: Decimal
    total_inc_vat_zar: Decimal


class SalesVatReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    invoice_count: int
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
