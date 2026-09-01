from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    direction: Literal["in", "out"]
    invoice_id: Optional[uuid.UUID] = None
    bill_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)
    fx_to_zar: Optional[Decimal] = None
    paid_on: datetime.date


class PaymentResponse(BaseModel):
    id: uuid.UUID
    payment_number: str
    direction: Literal["in", "out"]
    invoice_id: Optional[uuid.UUID]
    bill_id: Optional[uuid.UUID]
    amount: Decimal
    currency: str
    fx_to_zar: Decimal
    amount_zar: Decimal
    fx_gain_loss_zar: Decimal
    paid_on: datetime.date
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
