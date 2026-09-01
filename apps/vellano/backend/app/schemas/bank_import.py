from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BankImportLineResponse(BaseModel):
    id: uuid.UUID
    transaction_date: datetime.date
    description: str
    reference: Optional[str]
    amount_zar: Decimal
    matched_payment_id: Optional[uuid.UUID]
    matched_payment_number: Optional[str] = None
    suggested_payment_id: Optional[uuid.UUID] = None
    suggested_payment_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BankImportResponse(BaseModel):
    id: uuid.UUID
    filename: str
    line_count: int
    lines: list[BankImportLineResponse]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BankImportSummary(BaseModel):
    id: uuid.UUID
    filename: str
    line_count: int
    matched_count: int
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BankImportMatchRequest(BaseModel):
    payment_id: uuid.UUID


class AgedBucket(BaseModel):
    label: str
    amount_zar: Decimal


class AgedLine(BaseModel):
    document_number: str
    contact_name: str
    issue_date: datetime.date
    balance_zar: Decimal
    days_outstanding: int
    bucket: str


class AgedReport(BaseModel):
    as_of: datetime.date
    total_zar: Decimal
    buckets: list[AgedBucket]
    lines: list[AgedLine]


class ProfitLossLine(BaseModel):
    code: str
    name: str
    amount_zar: Decimal


class ProfitLossReport(BaseModel):
    from_date: datetime.date
    to_date: datetime.date
    income: list[ProfitLossLine]
    expenses: list[ProfitLossLine]
    total_income_zar: Decimal
    total_expenses_zar: Decimal
    net_profit_zar: Decimal


class BalanceSheetLine(BaseModel):
    code: str
    name: str
    type: Literal["asset", "liability", "income", "expense"]
    balance_zar: Decimal


class BalanceSheetReport(BaseModel):
    as_of: datetime.date
    assets: list[BalanceSheetLine]
    liabilities: list[BalanceSheetLine]
    equity_zar: Decimal
    total_assets_zar: Decimal
    total_liabilities_zar: Decimal


class Vat201Draft(BaseModel):
    period_from: datetime.date
    period_to: datetime.date
    vendor_name: str = "Vellano"
    vendor_vat_number: str = "4123456789"
    standard_rated_supplies_ex_vat: Decimal = Field(
        description="Field 1 — standard rated supplies (excl VAT)"
    )
    output_tax: Decimal = Field(description="Field 2 — output tax at 15%")
    input_tax: Decimal = Field(description="Field 3 — input tax")
    net_vat_payable: Decimal = Field(description="Field 4 — net VAT payable (output − input)")
    invoice_count: int
    credit_note_count: int
    disclaimer: str = (
        "Draft for manual entry into SARS eFiling only. "
        "This application does not file VAT returns or contact SARS."
    )
