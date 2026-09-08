from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import InvoiceLineCreate, InvoiceResponse


class RepeatingInvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    name: Optional[str] = None
    day_of_month: int = Field(ge=1, le=28)
    next_date: datetime.date
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class RepeatingInvoiceUpdate(BaseModel):
    name: Optional[str] = None
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    next_date: Optional[datetime.date] = None
    is_active: Optional[bool] = None


class RepeatingInvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_ex_vat: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class RepeatingInvoiceResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: Optional[str]
    day_of_month: int
    next_date: datetime.date
    is_active: bool
    created_by: Optional[uuid.UUID]
    lines: list[RepeatingInvoiceLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class RepeatingInvoiceRunResponse(BaseModel):
    schedule: RepeatingInvoiceResponse
    invoice: InvoiceResponse
