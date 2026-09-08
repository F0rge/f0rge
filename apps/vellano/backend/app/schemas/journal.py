from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.journal import JournalDocumentType, JournalStatus


class JournalLineCreate(BaseModel):
    account_id: uuid.UUID
    debit_zar: Decimal = Decimal("0")
    credit_zar: Decimal = Decimal("0")


class JournalCreate(BaseModel):
    entry_date: datetime.date
    memo: Optional[str] = Field(default=None, max_length=512)
    source: str = Field(default="manual", max_length=64)
    status: JournalStatus = JournalStatus.DRAFT
    lines: list[JournalLineCreate] = Field(min_length=2)


class JournalLineResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_code: str
    account_name: str
    debit_zar: Decimal
    credit_zar: Decimal

    model_config = ConfigDict(from_attributes=True)


class JournalResponse(BaseModel):
    id: uuid.UUID
    document_type: JournalDocumentType
    document_id: uuid.UUID
    memo: Optional[str]
    status: JournalStatus
    source: Optional[str]
    journal_number: Optional[str]
    entry_date: datetime.date
    voided_by_id: Optional[uuid.UUID]
    debit_total_zar: Decimal
    credit_total_zar: Decimal
    lines: list[JournalLineResponse]
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
