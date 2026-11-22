from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.schemas.payment import PaymentMethod

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
    # Percent off the line, priced like the till; needs till.discount.
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)

    @model_validator(mode="after")
    def unit_or_sku(self) -> "InvoiceLineCreate":
        if self.unit_ex_vat is None and self.sku_id is None:
            raise ValueError("Each line must have unit_ex_vat or sku_id")
        return self


class InvoicePaymentCreate(BaseModel):
    """Already paid: one payment of the full total, recorded with the invoice."""

    tender: PaymentMethod
    reference: Optional[str] = Field(default=None, max_length=200)
    paid_on: datetime.date


class InvoiceCreate(BaseModel):
    customer_id: uuid.UUID
    issue_date: datetime.date
    lines: list[InvoiceLineCreate] = Field(min_length=1)
    credit_override: bool = False
    credit_override_reason: Optional[str] = None
    note_printed: DocumentNote = None
    note_internal: DocumentNote = None
    # Defaults to the issue date plus the customer's payment terms.
    due_date: Optional[datetime.date] = None
    sales_staff_id: Optional[uuid.UUID] = None
    # None issues the invoice on account (unpaid, on the customer's statement).
    payment: Optional[InvoicePaymentCreate] = None

    @model_validator(mode="after")
    def due_after_issue(self) -> "InvoiceCreate":
        if self.due_date is not None and self.due_date < self.issue_date:
            raise ValueError("Due date cannot be before the issue date")
        if self.payment is not None and self.payment.paid_on < self.issue_date:
            raise ValueError("Paid on cannot be before the issue date")
        return self


def _catalogue_priced(lines: list[InvoiceLineCreate]) -> None:
    # Staff price product lines through discount_percent (gated by till.discount);
    # a typed unit would bypass that. Repeating invoices and seeds keep typed units.
    if any(line.sku_id is not None and line.unit_ex_vat is not None for line in lines):
        raise ValueError(
            "Product lines are priced from the catalogue: send discount_percent, not unit_ex_vat"
        )


class ManualInvoiceCreate(InvoiceCreate):
    """An invoice created by staff in the back office."""

    @model_validator(mode="after")
    def catalogue_priced(self) -> "ManualInvoiceCreate":
        _catalogue_priced(self.lines)
        return self


class InvoicePreviewRequest(BaseModel):
    """Price an invoice cart exactly as creating it would, without saving."""

    customer_id: uuid.UUID
    lines: list[InvoiceLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def catalogue_priced(self) -> "InvoicePreviewRequest":
        _catalogue_priced(self.lines)
        return self


class InvoiceSummary(BaseModel):
    outstanding_zar: Decimal
    outstanding_count: int
    overdue_zar: Decimal
    overdue_count: int
    on_statement_zar: Decimal
    on_statement_count: int
    paid_this_month_zar: Decimal
    paid_this_month_count: int


class InvoiceUpdate(BaseModel):
    """After issue only staff-facing fields change; the printed note is part of the document.

    Only the fields sent are changed.
    """

    model_config = ConfigDict(extra="forbid")

    note_internal: DocumentNote = None
    sales_staff_id: Optional[uuid.UUID] = None


InvoiceSource = Literal["till", "manual", "imported"]
InvoiceStatus = Literal["paid", "partially_paid", "unpaid", "on_statement", "overdue", "unknown"]


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: int
    unit_ex_vat: Decimal
    # Line discount %. None on lines stored before it was kept: their unit is already net.
    discount_percent: Optional[Decimal] = None
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
    source: InvoiceSource = "manual"
    # Paid, partly paid, unpaid, on statement or overdue; "unknown" for Cin7 imports.
    status: InvoiceStatus = "unpaid"
    is_archived: bool = False
    archived_at: Optional[datetime.datetime] = None
    sales_staff_id: Optional[uuid.UUID] = None
    sales_staff_name: Optional[str] = None
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
    source: InvoiceSource = "manual"
    # Paid, partly paid, unpaid, on statement or overdue; "unknown" for Cin7 imports.
    status: InvoiceStatus = "unpaid"
    is_archived: bool = False
    archived_at: Optional[datetime.datetime] = None
    note_printed: Optional[str] = None
    note_internal: Optional[str] = None
    sales_staff_id: Optional[uuid.UUID] = None
    sales_staff_name: Optional[str] = None
    prices_include_vat: bool
    lines: list[InvoiceLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
