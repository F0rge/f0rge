from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.schemas.quantity import Quantity

BillApproval = Literal["draft", "awaiting_approval", "approved"]
# Approval first, then settlement; ``overdue`` is an approved, unpaid bill past its due date.
BillStatus = Literal[
    "draft", "awaiting_approval", "unpaid", "partially_paid", "overdue", "paid", "unknown"
]


class BillLineCreate(BaseModel):
    description: str = Field(min_length=1)
    qty: int = Field(gt=0)
    unit_amount: Decimal = Field(gt=0)


class BillCreate(BaseModel):
    supplier_id: uuid.UUID
    supplier_ref: str = Field(min_length=1)
    issue_date: datetime.date
    # Defaults to 30 days after the issue date.
    due_date: Optional[datetime.date] = None
    currency: str = Field(min_length=3, max_length=8)
    fx_to_zar: Optional[Decimal] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    # Only an approved bill posts to the ledger; drafts are posted when approved.
    approval_status: BillApproval = "approved"
    lines: list[BillLineCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def due_after_issue(self):
        if self.due_date is not None and self.due_date < self.issue_date:
            raise ValueError("The due date can't be before the issue date")
        return self


class BillUpdate(BaseModel):
    due_date: Optional[datetime.date] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class BillLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    qty: Quantity
    unit_amount: Decimal
    amount_foreign: Decimal
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class BillAttachmentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: str
    uploaded_at: datetime.datetime
    uploaded_by_id: Optional[uuid.UUID]
    # The previous release's single file, not yet a bill_attachments row: download only.
    read_only: bool = False

    model_config = ConfigDict(from_attributes=True)


class BillListItem(BaseModel):
    is_archive: bool
    fx_rate_known: bool
    id: uuid.UUID
    bill_number: str
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_ref: str
    issue_date: datetime.date
    due_date: Optional[datetime.date]
    currency: str
    fx_to_zar: Decimal
    amount_foreign: Decimal
    amount_zar: Decimal
    amount_paid_zar: Decimal
    amount_paid_foreign: Decimal
    balance_zar: Decimal
    balance_foreign: Decimal
    payment_status: Literal["unpaid", "partially_paid", "paid", "unknown"]
    approval_status: BillApproval
    status: BillStatus
    is_archived: bool
    archived_at: Optional[datetime.datetime]
    notes: Optional[str]
    attachment_count: int
    purchase_order_id: Optional[uuid.UUID] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BillResponse(BillListItem):
    lines: list[BillLineResponse]
    attachments: list[BillAttachmentResponse]


class BillSummary(BaseModel):
    owing_zar: Decimal
    owing_count: int
    overdue_zar: Decimal
    overdue_count: int
    due_soon_zar: Decimal
    due_soon_count: int
    awaiting_approval_count: int
    draft_count: int
