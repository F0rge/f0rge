from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineCreate(BaseModel):
    description: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_ex_vat: Decimal = Field(gt=0)


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    issue_date: datetime.date
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_ex_vat: Decimal
    ex_vat: Decimal
    inc_vat: Decimal
    vat_amount: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    issue_date: datetime.date
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    lines: list[InvoiceLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
