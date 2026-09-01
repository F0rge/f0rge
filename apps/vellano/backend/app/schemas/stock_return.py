from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.stock_return import (
    StockReturnDisposition,
    StockReturnReason,
    StockReturnStatus,
)


class StockReturnLineCreate(BaseModel):
    invoice_line_id: uuid.UUID
    sku_id: Optional[uuid.UUID] = None
    qty: int = Field(gt=0)


class StockReturnCreate(BaseModel):
    invoice_id: uuid.UUID
    location_id: uuid.UUID
    reason: StockReturnReason
    disposition: StockReturnDisposition
    notes: Optional[str] = None
    lines: list[StockReturnLineCreate] = Field(min_length=1)


class StockReturnLineResponse(BaseModel):
    id: uuid.UUID
    invoice_line_id: uuid.UUID
    sku_id: Optional[uuid.UUID]
    description: str
    qty: int
    unit_ex_vat: Decimal

    model_config = ConfigDict(from_attributes=True)


class StockReturnResponse(BaseModel):
    id: uuid.UUID
    return_number: str
    invoice_id: uuid.UUID
    invoice_number: str
    location_id: uuid.UUID
    location_name: str
    credit_note_id: Optional[uuid.UUID]
    reason: StockReturnReason
    disposition: StockReturnDisposition
    status: StockReturnStatus
    notes: Optional[str]
    lines: list[StockReturnLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
