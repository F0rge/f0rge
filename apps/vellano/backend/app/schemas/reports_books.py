from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.models.journal import JournalDocumentType, JournalStatus


class TrialBalanceLine(BaseModel):
    code: str
    name: str
    debit_zar: Decimal
    credit_zar: Decimal


class TrialBalanceReport(BaseModel):
    as_of: datetime.date
    lines: list[TrialBalanceLine]
    total_debit_zar: Decimal
    total_credit_zar: Decimal


class JournalReportLine(BaseModel):
    account_code: str
    account_name: str
    debit_zar: Decimal
    credit_zar: Decimal


class JournalReportEntry(BaseModel):
    entry_date: datetime.date
    journal_number: Optional[str]
    document_type: JournalDocumentType
    source: Optional[str]
    memo: Optional[str]
    status: JournalStatus
    lines: list[JournalReportLine]


class JournalReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    source: Optional[str]
    entries: list[JournalReportEntry]


class CashSummaryAccount(BaseModel):
    code: str
    name: str
    cash_in_zar: Decimal
    cash_out_zar: Decimal
    net_zar: Decimal


class CashSummaryReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    accounts: list[CashSummaryAccount]
    total_cash_in_zar: Decimal
    total_cash_out_zar: Decimal
    total_net_zar: Decimal
