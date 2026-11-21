from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

NOTE_MAX_LENGTH = 2000

# A sale's printed or internal note; blank means none.
DocumentNote = Annotated[
    Optional[str],
    Field(max_length=NOTE_MAX_LENGTH),
    AfterValidator(lambda value: (value or "").strip() or None),
]


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
    note_printed: DocumentNote = None
    note_internal: DocumentNote = None


class InvoiceUpdate(BaseModel):
    """After issue only staff-facing fields change; the printed note is part of the document.

    Only the fields sent are changed.
    """

    model_config = ConfigDict(extra="forbid")

    note_internal: DocumentNote = None
    sales_staff_id: Optional[uuid.UUID] = None


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
    price_warning: Optional[str] = None
    till_no_stock_required: bool = False
    exclude_from_commission: bool = False
    # Computed on read. Not stored, and not printed on the customer PDF.
    suspect_price_warning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceListItem(BaseModel):
    is_archive: bool
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
    payment_status: Literal["unpaid", "partially_paid", "paid", "unknown"]
    on_account: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class InvoiceResponse(BaseModel):
    is_archive: bool
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
    payment_status: Literal["unpaid", "partially_paid", "paid", "unknown"]
    on_account: bool = False
    note_printed: Optional[str] = None
    note_internal: Optional[str] = None
    sales_staff_id: Optional[uuid.UUID] = None
    sales_staff_name: Optional[str] = None
    prices_include_vat: bool
    lines: list[InvoiceLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
