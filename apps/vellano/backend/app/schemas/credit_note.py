from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CreditNoteCreate(BaseModel):
    invoice_id: uuid.UUID
    reason: Optional[str] = None


class CreditNoteResponse(BaseModel):
    id: uuid.UUID
    credit_note_number: str
    invoice_id: uuid.UUID
    invoice_number: str
    reason: Optional[str]
    issue_date: datetime.date
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
