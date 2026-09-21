from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stock_adjustment import StockAdjustmentReason, StockAdjustmentStatus


class StockAdjustmentCreate(BaseModel):
    location_id: uuid.UUID
    reason: StockAdjustmentReason
    notes: Optional[str] = None


class StockAdjustmentLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty_delta: int
    unit_cost_zar: Optional[Decimal] = Field(default=None, gt=0)


class StockAdjustmentLineUpdate(BaseModel):
    qty_delta: Optional[int] = None
    unit_cost_zar: Optional[Decimal] = Field(default=None, gt=0)


class StockAdjustmentLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty_delta: int
    unit_cost_zar: Optional[Decimal]
    current_qty: int
    new_qty: int

    model_config = ConfigDict(from_attributes=True)


class StockAdjustmentResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    location_name: str
    reason: StockAdjustmentReason
    notes: Optional[str]
    status: StockAdjustmentStatus
    lines: list[StockAdjustmentLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
