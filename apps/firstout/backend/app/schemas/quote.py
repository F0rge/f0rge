from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quote import QuoteStatus


class QuoteLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    notes: Optional[str] = None


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    lines: list[QuoteLineCreate] = Field(min_length=1)
    notes: Optional[str] = None


class QuoteUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    lines: Optional[list[QuoteLineCreate]] = Field(default=None, min_length=1)
    notes: Optional[str] = None


class QuoteDeposit(BaseModel):
    amount: Decimal = Field(gt=0)
    tender: Literal["cash", "eft"]


class QuoteAccept(BaseModel):
    location_id: Optional[uuid.UUID] = None
    hold_stock: bool = False
    deposit: Optional[QuoteDeposit] = None


class QuoteLineResponse(BaseModel):
    id: uuid.UUID
    sku_id: uuid.UUID
    our_ref: str
    name: str
    qty: int
    unit_ex_vat: Decimal
    description: str
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class QuoteListItem(BaseModel):
    id: uuid.UUID
    quote_number: str
    customer_id: uuid.UUID
    customer_name: str
    status: QuoteStatus
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    notes: Optional[str]
    items_label: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteResponse(BaseModel):
    id: uuid.UUID
    quote_number: str
    customer_id: uuid.UUID
    customer_name: str
    status: QuoteStatus
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    notes: Optional[str]
    lines: list[QuoteLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
