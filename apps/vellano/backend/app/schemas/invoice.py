from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvoiceLineCreate(BaseModel):
    description: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_ex_vat: Optional[Decimal] = Field(default=None, gt=0)
    sku_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def unit_or_sku(self) -> "InvoiceLineCreate":
        if self.unit_ex_vat is None and self.sku_id is None:
            raise ValueError("Each line must have unit_ex_vat or sku_id")
        return self


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    issue_date: datetime.date
    lines: list[InvoiceLineCreate] = Field(min_length=1)
    credit_override: bool = False
    credit_override_reason: Optional[str] = None


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_ex_vat: Decimal
    ex_vat: Decimal
    inc_vat: Decimal
    vat_amount: Decimal
    sort_order: int
    sku_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    issue_date: datetime.date
    due_date: Optional[datetime.date] = None
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID
    customer_name: str
    issue_date: datetime.date
    due_date: Optional[datetime.date] = None
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    amount_paid: Decimal
    balance: Decimal
    source: str = "books"
    location_id: Optional[uuid.UUID] = None
    lines: list[InvoiceLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
