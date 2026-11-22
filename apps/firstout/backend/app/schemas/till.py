from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.invoice import DocumentNote, InvoiceLineResponse


from app.schemas.quantity import Quantity


class TillSaleLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)


class TillPriceRequest(BaseModel):
    lines: list[TillSaleLineCreate] = Field(min_length=1)
    customer_id: Optional[uuid.UUID] = None


TillTender = Literal["statement", "cash", "card", "deposit", "eft"]


class TillSaleCreate(TillPriceRequest):
    location_id: uuid.UUID
    # "statement" issues the invoice unpaid, on account; no payment is recorded.
    tender: TillTender
    # Defaults to issue date + payment terms; must not be before the issue date.
    due_date: Optional[datetime.date] = None
    price_revision: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    pick_id: Optional[uuid.UUID] = None
    pick_ids: list[uuid.UUID] = Field(default_factory=list)
    credit_override: bool = False
    credit_override_reason: Optional[str] = None
    # Complete from the caller's server basket; it is emptied with the sale.
    basket_id: Optional[uuid.UUID] = None
    basket_version: Optional[int] = Field(default=None, ge=1)
    note_printed: DocumentNote = None
    note_internal: DocumentNote = None
    # Required when the business has an active sales colleague.
    sales_staff_id: Optional[uuid.UUID] = None
    # The open quote this sale converts; it is marked converted with the sale.
    quote_id: Optional[uuid.UUID] = None


class TillSaleLocationStock(BaseModel):
    location_id: uuid.UUID
    location_name: str
    on_hand: Quantity


class TillSaleResponse(BaseModel):
    invoice_id: uuid.UUID
    # The draft pick for units reserved against the invoice, when stock was sold from elsewhere.
    pick_id: Optional[uuid.UUID] = None
    invoice_number: str
    # None for a statement sale: nothing is paid at the till.
    payment_id: Optional[uuid.UUID] = None
    payment_number: Optional[str] = None
    tender: TillTender
    issue_date: datetime.date
    due_date: Optional[datetime.date] = None
    on_account: bool = False
    # The quote the sale converted.
    quote_number: Optional[str] = None
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    prices_include_vat: bool
    lines: list[InvoiceLineResponse]
    location: TillSaleLocationStock

    model_config = ConfigDict(from_attributes=True)
