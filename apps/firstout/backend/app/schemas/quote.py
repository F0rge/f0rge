from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.quote import QuoteStatus
from app.schemas.invoice import DocumentNote


class QuoteLineCreate(BaseModel):
    sku_id: uuid.UUID
    qty: int = Field(gt=0)
    notes: Optional[str] = None
    # Staff override. Omitted on an existing line keeps that line's price until a confirmed reprice.
    unit_ex_vat: Optional[Decimal] = Field(default=None, gt=0)
    # Percent off the line total. Omitted means no discount. Does not change unit_ex_vat.
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    lines: list[QuoteLineCreate] = Field(min_length=1)
    # Printed on the quote.
    notes: Optional[str] = None
    internal_note: DocumentNote = None
    # Defaults to 14 days after the quote is created.
    valid_until: Optional[datetime.date] = None
    sales_staff_id: Optional[uuid.UUID] = None


class QuoteUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    lines: Optional[list[QuoteLineCreate]] = Field(default=None, min_length=1)
    notes: Optional[str] = None
    internal_note: DocumentNote = None
    valid_until: Optional[datetime.date] = None
    sales_staff_id: Optional[uuid.UUID] = None


class QuoteReplace(QuoteUpdate):
    """PUT: the editor's whole quote; omitted notes, validity or colleague are cleared."""

    customer_id: uuid.UUID
    lines: list[QuoteLineCreate] = Field(min_length=1)


class QuotePreviewRequest(BaseModel):
    """Price a quote cart exactly as saving it would, without saving."""

    customer_id: uuid.UUID
    lines: list[QuoteLineCreate] = Field(min_length=1)
    # The quote being edited: its lines keep their saved prices.
    quote_id: Optional[uuid.UUID] = None


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
    discount_percent: Decimal
    description: str
    notes: Optional[str]
    price_warning: Optional[str] = None
    # Computed on read. Not stored, and not printed on the customer PDF.
    suspect_price_warning: Optional[str] = None

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
    sales_staff_id: Optional[uuid.UUID] = None
    sales_staff_name: Optional[str] = None
    valid_until: Optional[datetime.date] = None
    issue_date: datetime.date
    converted_invoice_id: Optional[uuid.UUID] = None
    converted_invoice_number: Optional[str] = None
    # Converted (till) or accepted (sales order): read-only. The workspace lifecycle field.
    is_converted: bool = False
    # Open, Expired (past valid_until), Converted, Accepted or Cancelled.
    state: str
    item_count: int
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
    # The rate the amounts use (0.15 is 15%), stored with the document (ADR 0003).
    vat_rate: Decimal
    notes: Optional[str]
    internal_note: Optional[str] = None
    sales_staff_id: Optional[uuid.UUID] = None
    valid_until: Optional[datetime.date] = None
    issue_date: datetime.date
    converted_invoice_id: Optional[uuid.UUID] = None
    converted_invoice_number: Optional[str] = None
    prices_include_vat: bool
    lines: list[QuoteLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
