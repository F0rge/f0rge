from __future__ import annotations

import csv
import datetime
import io
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from f0rge_core.exceptions import ValidationError

from app.services.bank_csv import _find_column, _parse_amount, _parse_date
from app.services.vat import CENT

DATE_HEADERS = ("date", "transaction date")
NARRATION_HEADERS = ("narration", "description", "memo")
ACCOUNT_HEADERS = ("account", "account code", "code")
DEBIT_HEADERS = ("debit", "debit amount")
CREDIT_HEADERS = ("credit", "credit amount")

DEFAULT_NARRATION = "SimplePay import"


@dataclass
class JournalCsvError:
    row: int
    message: str


@dataclass
class JournalCsvLine:
    row: int
    entry_date: Optional[datetime.date]
    narration: str
    account_code: str
    debit_zar: Decimal
    credit_zar: Decimal


@dataclass
class JournalCsvParse:
    lines: list[JournalCsvLine]
    errors: list[JournalCsvError] = field(default_factory=list)
    debit_total: Decimal = Decimal("0.00")
    credit_total: Decimal = Decimal("0.00")
    entry_date: Optional[datetime.date] = None
    narration: str = DEFAULT_NARRATION


def parse_journal_csv(content: bytes) -> JournalCsvParse:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV file is unreadable") from exc

    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValidationError("CSV file is empty")

    headers = rows[0]
    date_col = _find_column(headers, DATE_HEADERS)
    narration_col = _find_column(headers, NARRATION_HEADERS)
    account_col = _find_column(headers, ACCOUNT_HEADERS)
    debit_col = _find_column(headers, DEBIT_HEADERS)
    credit_col = _find_column(headers, CREDIT_HEADERS)

    if date_col is None:
        raise ValidationError("CSV must include a Date column")
    if narration_col is None:
        raise ValidationError("CSV must include a Narration column")
    if account_col is None:
        raise ValidationError("CSV must include an Account column")
    if debit_col is None or credit_col is None:
        raise ValidationError("CSV must include Debit and Credit columns")

    parsed = JournalCsvParse(lines=[])
    needed = max(date_col, narration_col, account_col, debit_col, credit_col)
    for row_num, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        line, row_errors = _parse_row(
            row_num,
            row,
            needed,
            date_col,
            narration_col,
            account_col,
            debit_col,
            credit_col,
        )
        parsed.lines.append(line)
        parsed.errors.extend(row_errors)
        xor_ok = (line.debit_zar > 0 and line.credit_zar == 0) or (
            line.credit_zar > 0 and line.debit_zar == 0
        )
        if xor_ok:
            parsed.debit_total += line.debit_zar
            parsed.credit_total += line.credit_zar
        if parsed.entry_date is None and line.entry_date is not None:
            parsed.entry_date = line.entry_date
        if parsed.narration == DEFAULT_NARRATION and line.narration:
            parsed.narration = line.narration

    parsed.debit_total = parsed.debit_total.quantize(CENT)
    parsed.credit_total = parsed.credit_total.quantize(CENT)
    if len(parsed.lines) < 2:
        parsed.errors.append(JournalCsvError(row=0, message="Journal must have at least two lines"))
    if parsed.debit_total != parsed.credit_total:
        parsed.errors.append(JournalCsvError(row=0, message="Journal entry must balance"))
    return parsed


def _parse_row(
    row_num: int,
    row: list[str],
    needed: int,
    date_col: int,
    narration_col: int,
    account_col: int,
    debit_col: int,
    credit_col: int,
) -> tuple[JournalCsvLine, list[JournalCsvError]]:
    errors: list[JournalCsvError] = []
    if len(row) <= needed:
        row = list(row) + [""] * (needed + 1 - len(row))

    entry_date: Optional[datetime.date] = None
    raw_date = row[date_col].strip()
    if not raw_date:
        errors.append(JournalCsvError(row=row_num, message="date is required"))
    else:
        try:
            entry_date = _parse_date(raw_date)
        except ValidationError as exc:
            errors.append(JournalCsvError(row=row_num, message=exc.detail))

    narration = row[narration_col].strip()
    account_code = row[account_col].strip()
    if not account_code:
        errors.append(JournalCsvError(row=row_num, message="account code is required"))

    debit_zar = Decimal("0.00")
    credit_zar = Decimal("0.00")
    raw_debit = row[debit_col].strip()
    raw_credit = row[credit_col].strip()
    try:
        debit_zar = _parse_amount(raw_debit).quantize(CENT) if raw_debit else Decimal("0.00")
    except ValidationError as exc:
        errors.append(JournalCsvError(row=row_num, message=exc.detail))
    try:
        credit_zar = _parse_amount(raw_credit).quantize(CENT) if raw_credit else Decimal("0.00")
    except ValidationError as exc:
        errors.append(JournalCsvError(row=row_num, message=exc.detail))

    debit_ok = debit_zar > 0 and credit_zar == 0
    credit_ok = credit_zar > 0 and debit_zar == 0
    if not debit_ok and not credit_ok:
        errors.append(
            JournalCsvError(row=row_num, message="Each line must be debit or credit, not both")
        )

    return (
        JournalCsvLine(
            row=row_num,
            entry_date=entry_date,
            narration=narration,
            account_code=account_code,
            debit_zar=debit_zar,
            credit_zar=credit_zar,
        ),
        errors,
    )
