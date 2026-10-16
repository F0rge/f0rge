from __future__ import annotations

import csv
import datetime
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

CURRENCIES = {"ZAR", "USD", "EUR", "GBP", "AUD", "CNY"}
# Cin7 product exports number price tiers and do not name them. Tier 1 is
# stored as retail and tier 2 as wholesale until a human confirms the map.
RETAIL_TIER = 1
WHOLESALE_TIER = 2
FILL_DOWN_KEYS = {"sku", "product", "productname", "productsku"}
BARCODE_LIMIT = 64


def header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def clip(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:limit]


def as_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "1"}


def money(value: object, places: str = "0.01") -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return Decimal(text).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def integral_qty(value: object) -> tuple[Optional[int], Optional[str]]:
    if value is None:
        return None, "blank quantity"
    text = str(value).strip()
    if text == "":
        return None, "blank quantity"
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None, "quantity is not a number"
    if number <= 0:
        return None, "quantity is not a positive integer"
    if number != number.to_integral_value():
        return None, "quantity is fractional"
    return int(number), None


def parse_date(value: object) -> Optional[datetime.date]:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def find_file(directory: Path, prefix: str, suffix: str) -> Optional[Path]:
    matches = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.startswith(prefix) and path.name.lower().endswith(suffix)
    )
    if not matches:
        return None
    return matches[0]


def realign_status_row(header: list[str], row: list[str]) -> tuple[list[str], bool]:
    """Repair a Cin7 party row whose Status cell is actually the currency.

    A shifted export puts ZAR in Status and a non-currency in Currency. Insert
    Active into the Status position so the remaining cells line up.
    """
    cells = [cell.strip() for cell in row]
    while len(cells) > len(header) and cells[-1] == "":
        cells.pop()
    if len(cells) < len(header):
        cells.extend([""] * (len(header) - len(cells)))
    try:
        status_i = header.index("Status")
        currency_i = header.index("Currency")
    except ValueError:
        return cells[: len(header)], False
    status = cells[status_i].upper()
    currency = cells[currency_i].upper()
    if status in CURRENCIES and currency not in CURRENCIES:
        cells = cells[:status_i] + ["Active"] + cells[status_i:]
        return cells[: len(header)], True
    return cells[: len(header)], False


def fill_down(header: list[str], rows: list[list[str]]) -> tuple[list[list[str]], int]:
    """Copy SKU and product name onto following blank cells.

    Cin7 detail sheets repeat a product as a block: the first line has the SKU
    and name, and later lines leave those cells blank.
    """
    indexes = [index for index, name in enumerate(header) if header_key(name) in FILL_DOWN_KEYS]
    last: dict[int, str] = {}
    filled = 0
    for row in rows:
        for index in indexes:
            if row[index]:
                last[index] = row[index]
            elif last.get(index):
                row[index] = last[index]
                filled += 1
    return rows, filled


def assign_barcodes(
    pairs: list[tuple[str, str]],
    taken: set[str],
) -> dict[str, tuple[str, bool]]:
    """Give every SKU a unique barcode.

    The first product code (sorted) keeps a shared Cin7 barcode. Later sharers
    and blank barcodes get ``CIN7-{code}``.
    """
    ordered = sorted(pairs, key=lambda item: item[0])
    owners: dict[str, list[str]] = {}
    for code, raw in ordered:
        barcode = raw.strip()
        if barcode:
            owners.setdefault(barcode, []).append(code)
    claimed = set(taken)
    assigned: dict[str, tuple[str, bool]] = {}
    for code, raw in ordered:
        barcode = raw.strip()
        keep = bool(barcode) and owners.get(barcode, [None])[0] == code and barcode not in claimed
        if keep:
            chosen = barcode[:BARCODE_LIMIT]
            generated = False
        else:
            chosen = _generated_barcode(code, claimed)
            generated = True
        claimed.add(chosen)
        assigned[code] = (chosen, generated)
    return assigned


def _generated_barcode(code: str, claimed: set[str]) -> str:
    base = f"CIN7-{code}"
    candidate = base[:BARCODE_LIMIT]
    number = 2
    while candidate in claimed or not candidate:
        suffix = f"-{number}"
        candidate = base[: BARCODE_LIMIT - len(suffix)] + suffix
        number += 1
    return candidate


def read_csv_records(path: Path, realign: bool = False) -> tuple[list[dict[str, str]], int]:
    text = path.read_text(encoding="utf-8-sig")
    parsed = list(csv.reader(text.splitlines()))
    if not parsed:
        return [], 0
    header = [cell.strip() for cell in parsed[0]]
    records: list[dict[str, str]] = []
    realigned = 0
    for raw in parsed[1:]:
        if not any(cell.strip() for cell in raw):
            continue
        if realign:
            cells, shifted = realign_status_row(header, raw)
            realigned += int(shifted)
        else:
            cells = [cell.strip() for cell in raw]
            while len(cells) > len(header) and cells[-1] == "":
                cells.pop()
            if len(cells) < len(header):
                cells.extend([""] * (len(header) - len(cells)))
            cells = cells[: len(header)]
        records.append({header[index]: cells[index] for index in range(len(header))})
    return records, realigned


def read_xlsx_all(path: Path) -> tuple[list[dict[str, str]], int]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["All"]
        iterator = sheet.iter_rows(values_only=True)
        header_row = next(iterator)
        header: list[str] = []
        for cell in header_row:
            if cell is None:
                break
            header.append(str(cell).strip())
        matrix: list[list[str]] = []
        for raw in iterator:
            values: list[str] = []
            for index in range(len(header)):
                cell = raw[index] if raw is not None and index < len(raw) else None
                values.append(_cell_text(cell))
            if any(values):
                matrix.append(values)
    finally:
        workbook.close()
    matrix, filled = fill_down(header, matrix)
    records = [{header[index]: row[index] for index in range(len(header))} for row in matrix]
    return records, filled


def _cell_text(cell: object) -> str:
    if cell is None:
        return ""
    if isinstance(cell, datetime.datetime):
        return cell.date().isoformat()
    if isinstance(cell, datetime.date):
        return cell.isoformat()
    return str(cell).strip()


def positive_int(value: str) -> Optional[int]:
    number = money(value, "1")
    if number is None or number < 1:
        return None
    if number != number.to_integral_value():
        return None
    return int(number)


def carton_count(value: str) -> int:
    parsed = positive_int(value)
    if parsed is None:
        return 1
    return parsed


def reorder_min(value: str) -> Optional[int]:
    return positive_int(value)
