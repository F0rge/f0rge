from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ShortName = Annotated[
    Optional[str],
    Field(max_length=32),
    AfterValidator(lambda value: (value or "").strip() or None),
]
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class SalesStaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    short_name: ShortName = None
    commission_rate: Rate = Decimal(0)
    is_active: bool = True


class SalesStaffUpdate(BaseModel):
    """Only the fields sent are changed. ``is_active: false`` deactivates."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[Name] = None
    short_name: ShortName = None
    commission_rate: Optional[Rate] = None
    is_active: Optional[bool] = None


class SalesStaffResponse(BaseModel):
    id: uuid.UUID
    name: str
    short_name: Optional[str]
    commission_rate: Decimal
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class SalesStaffOption(BaseModel):
    """What the till and invoice screens need: no commission rate."""

    id: uuid.UUID
    name: str
    short_name: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class CommissionDocument(BaseModel):
    """An invoice (positive) or credit note (deduction) counted in the month."""

    kind: str  # "invoice" | "credit_note"
    id: uuid.UUID
    number: str
    invoice_id: uuid.UUID
    invoice_number: str
    issue_date: datetime.date
    customer_name: str
    commissionable_ex_vat: Decimal
    excluded_ex_vat: Decimal


class CommissionRow(BaseModel):
    # None is the "unattributed" bucket: invoices with no sales colleague.
    sales_staff_id: Optional[uuid.UUID]
    name: str
    short_name: Optional[str] = None
    is_active: bool = True
    commission_rate: Decimal
    invoice_count: int
    commissionable_ex_vat: Decimal
    excluded_ex_vat: Decimal
    credit_deductions: Decimal
    net_commissionable: Decimal
    commission: Decimal
    documents: list[CommissionDocument]


class CommissionReport(BaseModel):
    month: str
    from_date: datetime.date
    to_date: datetime.date
    rows: list[CommissionRow]
    unattributed: CommissionRow
    invoice_count: int
    commissionable_ex_vat: Decimal
    excluded_ex_vat: Decimal
    credit_deductions: Decimal
    net_commissionable: Decimal
    commission: Decimal
