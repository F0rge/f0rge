from __future__ import annotations

import csv
import datetime
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from f0rge_core.exceptions import ValidationError

# SA bank CSV column aliases (case-insensitive).
DATE_HEADERS = ("date", "transaction date", "posting date", "value date")
DESCRIPTION_HEADERS = ("description", "narrative", "details", "transaction description")
REFERENCE_HEADERS = ("reference", "ref", "transaction reference")
AMOUNT_HEADERS = ("amount", "transaction amount", "signed amount")
DEBIT_HEADERS = ("debit", "debit amount", "money out")
CREDIT_HEADERS = ("credit", "credit amount", "money in")

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")


def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def _find_column(headers: list[str], aliases: tuple[str, ...]) -> Optional[int]:
    normalized = [_normalize_header(h) for h in headers]
    for alias in aliases:
        if alias in normalized:
            return normalized.index(alias)
    return None


def _parse_date(value: str) -> datetime.date:
    cleaned = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise ValidationError(f"Unrecognised date format: {value}")


def _parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace(" ", "").replace(",", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid amount: {value}") from exc


def parse_bank_csv(content: bytes) -> list[dict[str, object]]:
    """Parse SA bank CSV into line dicts with transaction_date, description, reference, amount_zar."""
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValidationError("CSV file is empty")

    headers = rows[0]
    date_col = _find_column(headers, DATE_HEADERS)
    desc_col = _find_column(headers, DESCRIPTION_HEADERS)
    ref_col = _find_column(headers, REFERENCE_HEADERS)
    amount_col = _find_column(headers, AMOUNT_HEADERS)
    debit_col = _find_column(headers, DEBIT_HEADERS)
    credit_col = _find_column(headers, CREDIT_HEADERS)

    if date_col is None:
        raise ValidationError("CSV must include a Date column")
    if desc_col is None:
        raise ValidationError("CSV must include a Description column")
    if amount_col is None and (debit_col is None or credit_col is None):
        raise ValidationError(
            "CSV must include either a signed Amount column or Debit and Credit columns"
        )

    lines: list[dict[str, object]] = []
    for row_num, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) <= max(
            i
            for i in (date_col, desc_col, ref_col, amount_col, debit_col, credit_col)
            if i is not None
        ):
            raise ValidationError(f"Row {row_num}: not enough columns")

        transaction_date = _parse_date(row[date_col])
        description = row[desc_col].strip()
        if not description:
            raise ValidationError(f"Row {row_num}: description is required")

        reference = row[ref_col].strip() if ref_col is not None and row[ref_col].strip() else None

        if amount_col is not None:
            amount_zar = _parse_amount(row[amount_col])
        else:
            debit = _parse_amount(row[debit_col]) if row[debit_col].strip() else Decimal(0)
            credit = _parse_amount(row[credit_col]) if row[credit_col].strip() else Decimal(0)
            if debit > 0 and credit > 0:
                raise ValidationError(f"Row {row_num}: both debit and credit are set")
            amount_zar = credit - debit

        if amount_zar == 0:
            raise ValidationError(f"Row {row_num}: amount must be non-zero")

        lines.append(
            {
                "transaction_date": transaction_date,
                "description": description,
                "reference": reference,
                "amount_zar": amount_zar,
            }
        )

    if not lines:
        raise ValidationError("CSV contains no transaction rows")

    return lines
