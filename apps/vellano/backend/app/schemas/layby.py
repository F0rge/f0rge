from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.layby import LaybyStatus


class LaybyLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)


class LaybyCreate(BaseModel):
    customer_id: uuid.UUID
    location_id: uuid.UUID
    due_date: datetime.date
    hold_stock: bool
    deposit_amount: Decimal = Field(gt=0)
    tender: Literal["cash", "card"]
    lines: list[LaybyLineCreate] = Field(min_length=1)
    notes: Optional[str] = None


class LaybyPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    tender: Literal["cash", "card"]


class LaybyLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: int
    unit_ex_vat: Decimal

    model_config = ConfigDict(from_attributes=True)


class LaybyPaymentResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    tender: str
    paid_on: datetime.date

    model_config = ConfigDict(from_attributes=True)


class LaybyResponse(BaseModel):
    id: uuid.UUID
    layby_number: str
    customer_id: uuid.UUID
    customer_name: str
    location_id: uuid.UUID
    location_name: str
    invoice_id: Optional[uuid.UUID]
    due_date: datetime.date
    hold_stock: bool
    status: LaybyStatus
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    notes: Optional[str]
    lines: list[LaybyLineResponse]
    payments: list[LaybyPaymentResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
