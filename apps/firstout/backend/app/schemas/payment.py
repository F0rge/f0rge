from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

PaymentMethod = Literal["eft", "card", "cash", "other"]


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip() or None


class PaymentCreate(BaseModel):
    direction: Literal["in", "out"]
    invoice_id: Optional[uuid.UUID] = None
    bill_id: Optional[uuid.UUID] = None
    amount: Decimal
    currency: str = Field(min_length=3, max_length=8)
    fx_to_zar: Optional[Decimal] = None
    paid_on: datetime.date
    tender: Optional[PaymentMethod] = None
    reference: Optional[str] = Field(default=None, max_length=200)

    _strip_reference = field_validator("reference")(_blank_to_none)


class PaymentVoid(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Give a reason for voiding this payment")
        return value.strip()


class PaymentOpenDocument(BaseModel):
    """An invoice or bill that still has a balance a payment can settle."""

    kind: Literal["invoice", "bill"]
    document_id: uuid.UUID
    number: str
    contact_name: str
    issue_date: datetime.date
    currency: str
    fx_to_zar: Decimal
    outstanding_foreign: Decimal
    outstanding_zar: Decimal

    model_config = ConfigDict(from_attributes=True)


class PaymentSummary(BaseModel):
    received_this_month_zar: Decimal
    received_this_month_count: int
    paid_this_month_zar: Decimal
    paid_this_month_count: int
    unreconciled_count: int
    unreconciled_net_zar: Decimal


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
    tender: Optional[Literal["cash", "card", "deposit", "eft", "other"]] = None
    reference: Optional[str] = None
    party_name: Optional[str] = None
    document_number: Optional[str] = None
    is_reconciled: bool = False
    reconciled_at: Optional[datetime.datetime] = None
    is_voided: bool = False
    voided_at: Optional[datetime.datetime] = None
    void_reason: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
