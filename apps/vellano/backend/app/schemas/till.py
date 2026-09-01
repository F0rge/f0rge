from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import InvoiceLineResponse


class TillSaleLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)


class TillSaleCreate(BaseModel):
    location_id: uuid.UUID
    lines: list[TillSaleLineCreate] = Field(min_length=1)
    tender: Literal["cash", "card"]


class TillSaleLocationStock(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: int


class TillSaleResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    payment_id: uuid.UUID
    payment_number: str
    tender: Literal["cash", "card"]
    issue_date: datetime.date
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    lines: list[InvoiceLineResponse]
    location: TillSaleLocationStock

    model_config = ConfigDict(from_attributes=True)
