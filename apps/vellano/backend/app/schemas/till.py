from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import InvoiceLineResponse


class TillSaleLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class TillSaleCreate(BaseModel):
    location_id: uuid.UUID
    lines: list[TillSaleLineCreate] = Field(min_length=1)
    tender: Literal["cash", "card", "deposit", "eft"]
    customer_id: Optional[uuid.UUID] = None
    credit_override: bool = False
    credit_override_reason: Optional[str] = None


class TillSaleLocationStock(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: int


class TillSaleResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    payment_id: uuid.UUID
    payment_number: str
    tender: Literal["cash", "card", "deposit", "eft"]
    issue_date: datetime.date
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    lines: list[InvoiceLineResponse]
    location: TillSaleLocationStock

    model_config = ConfigDict(from_attributes=True)
