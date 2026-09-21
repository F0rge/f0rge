from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class JournalImportRowError(BaseModel):
    row: int
    message: str


class JournalImportPreviewLine(BaseModel):
    row: int
    account_code: str
    debit_zar: Decimal
    credit_zar: Decimal


class JournalImportPreviewResponse(BaseModel):
    lines: list[JournalImportPreviewLine]
    errors: list[JournalImportRowError] = Field(default_factory=list)
    balanced: bool
    debit_total: Decimal
    credit_total: Decimal
    entry_date: Optional[datetime.date] = None
    narration: str
