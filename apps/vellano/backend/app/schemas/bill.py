from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BillLineCreate(BaseModel):
    description: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_amount: Decimal = Field(gt=0)


class BillCreate(BaseModel):
    supplier_id: uuid.UUID
    supplier_ref: str = Field(min_length=1)
    issue_date: datetime.date
    currency: str = Field(min_length=3, max_length=8)
    fx_to_zar: Optional[Decimal] = None
    lines: list[BillLineCreate] = Field(min_length=1)


class BillLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_amount: Decimal
    amount_foreign: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class BillResponse(BaseModel):
    id: uuid.UUID
    bill_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_ref: str
    issue_date: datetime.date
    currency: str
    fx_to_zar: Decimal
    amount_foreign: Decimal
    amount_zar: Decimal
    amount_paid_zar: Decimal
    balance_zar: Decimal
    pdf_storage_key: Optional[str]
    lines: list[BillLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
