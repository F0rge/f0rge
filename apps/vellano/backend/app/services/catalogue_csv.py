from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from f0rge_core.exceptions import ValidationError

from app.services.vat import validate_non_negative_price

INVENTORY_ALIASES: dict[str, tuple[str, ...]] = {
    "our_ref": ("sku", "itemcode", "item code", "our ref", "product code"),
    "name": ("name", "product name", "description"),
    "category": ("category", "cat"),
    "retail_inc_vat": ("retail price", "price", "pricezar", "retail", "retail price zar"),
    "barcode": ("barcode", "ean", "upc", "our barcode"),
    "cost_zar": ("cost", "cost price", "landed cost"),
    "carton_count": ("carton count", "cartons", "carton_count"),
}

SOH_ALIASES: dict[str, tuple[str, ...]] = {
    "our_ref": ("sku", "itemcode", "item code", "our ref"),
    "location": ("location", "location name", "warehouse"),
    "qty": ("qty", "quantity", "on hand", "soh"),
    "unit_cost_zar": ("unit cost", "cost"),
}

INVENTORY_REQUIRED = ("our_ref", "name", "category", "retail_inc_vat")
SOH_REQUIRED = ("our_ref", "location", "qty")
INVENTORY_FIELDS = (
    "our_ref",
    "name",
    "category",
    "retail_inc_vat",
    "barcode",
    "cost_zar",
    "carton_count",
)
SOH_FIELDS = ("our_ref", "location", "qty", "unit_cost_zar")


@dataclass
class CsvRowError:
    row: int
    message: str


@dataclass
class InventoryCsvRow:
    row: int
    our_ref: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    retail_inc_vat: Optional[Decimal] = None
    barcode: Optional[str] = None
    cost_zar: Optional[Decimal] = None
    carton_count: Optional[int] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class SohCsvRow:
    row: int
    our_ref: Optional[str] = None
    location: Optional[str] = None
    qty: Optional[int] = None
    unit_cost_zar: Optional[Decimal] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class InventoryCsvParse:
    headers: list[str]
    suggested_map: dict[str, str]
    applied_map: dict[str, str]
    sample_row: dict[str, str]
    row_count: int
    rows: list[InventoryCsvRow]
    errors: list[CsvRowError]


@dataclass
class SohCsvParse:
    headers: list[str]
    suggested_map: dict[str, str]
    applied_map: dict[str, str]
    sample_row: dict[str, str]
    row_count: int
    rows: list[SohCsvRow]
    errors: list[CsvRowError]


def _normalize_header(header: str) -> str:
    collapsed = re.sub(r"\s+", " ", header.strip().lower().replace("_", " "))
    return collapsed


def suggest_column_map(headers: list[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, str]:
    normalized_to_original: dict[str, str] = {}
    for header in headers:
        key = _normalize_header(header)
        if key and key not in normalized_to_original:
            normalized_to_original[key] = header

    suggested: dict[str, str] = {}
    used: set[str] = set()
    for field_name, field_aliases in aliases.items():
        candidates = (_normalize_header(field_name),) + tuple(
            _normalize_header(alias) for alias in field_aliases
        )
        for candidate in candidates:
            original = normalized_to_original.get(candidate)
            if original is not None and original not in used:
                suggested[field_name] = original
                used.add(original)
                break
    return suggested


def parse_column_map_json(
    raw: Optional[str], allowed_keys: tuple[str, ...]
) -> Optional[dict[str, str]]:
    if raw is None or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid column map JSON") from exc
    if not isinstance(data, dict):
        raise ValidationError("Invalid column map JSON")

    allowed = set(allowed_keys)
    parsed: dict[str, str] = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        parsed[key] = value.strip()
    return parsed


def resolve_applied_map(
    headers: list[str],
    suggested_map: dict[str, str],
    user_map: Optional[dict[str, str]],
) -> tuple[dict[str, str], list[CsvRowError]]:
    if user_map is None:
        return suggested_map, []

    by_normalized = {_normalize_header(header): header for header in headers if header.strip()}
    applied: dict[str, str] = {}
    errors: list[CsvRowError] = []
    for field_name, header_name in user_map.items():
        matched = by_normalized.get(_normalize_header(header_name))
        if matched is None:
            errors.append(
                CsvRowError(row=1, message=f"Column '{header_name}' not found for {field_name}")
            )
            applied[field_name] = header_name
            continue
        applied[field_name] = matched
    return applied, errors


def read_csv_table(content: bytes) -> tuple[list[str], list[tuple[int, list[str]]]]:
    if not content or not content.strip():
        raise ValidationError("CSV file is empty")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV file is unreadable") from exc

    rows = list(csv.reader(io.StringIO(text)))
    if not rows or not any(cell.strip() for cell in rows[0]):
        raise ValidationError("CSV file is empty")

    headers = rows[0]
    data_rows: list[tuple[int, list[str]]] = []
    for row_num, row in enumerate(rows[1:], start=2):
        if not row or all(not cell.strip() for cell in row):
            continue
        data_rows.append((row_num, row))
    if not data_rows:
        raise ValidationError("CSV contains no data rows")
    return headers, data_rows


def _row_dict(headers: list[str], cells: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for index, header in enumerate(headers):
        values[header] = cells[index].strip() if index < len(cells) else ""
    return values


def _cell(headers: list[str], cells: list[str], mapped_header: str) -> str:
    target = _normalize_header(mapped_header)
    for index, header in enumerate(headers):
        if _normalize_header(header) == target:
            if index >= len(cells):
                return ""
            return cells[index].strip()
    return ""


def _parse_money(value: str, field_name: str) -> Decimal:
    cleaned = value.replace(" ", "").replace(",", "")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValidationError(f"Invalid {field_name}: {value}") from exc
    validate_non_negative_price(amount, field_name)
    return amount


def _parse_qty(value: str) -> int:
    if not re.fullmatch(r"\d+", value):
        raise ValidationError(f"qty must be an integer ≥ 0: {value}")
    return int(value)


def _parse_carton_count(value: str) -> int:
    if not re.fullmatch(r"[1-9]\d*", value):
        raise ValidationError(f"carton_count must be an integer ≥ 1: {value}")
    return int(value)


def _missing_column_errors(
    applied_map: dict[str, str], required: tuple[str, ...]
) -> list[CsvRowError]:
    errors: list[CsvRowError] = []
    for field_name in required:
        if field_name not in applied_map:
            label = "Category" if field_name == "category" else field_name
            errors.append(CsvRowError(row=1, message=f"{label} column is required"))
    return errors


def parse_inventory_csv(content: bytes, map_json: Optional[str] = None) -> InventoryCsvParse:
    headers, data_rows = read_csv_table(content)
    suggested_map = suggest_column_map(headers, INVENTORY_ALIASES)
    user_map = parse_column_map_json(map_json, INVENTORY_FIELDS)
    applied_map, map_errors = resolve_applied_map(headers, suggested_map, user_map)
    errors = list(map_errors)
    errors.extend(_missing_column_errors(applied_map, INVENTORY_REQUIRED))

    parsed_rows: list[InventoryCsvRow] = []
    for row_num, cells in data_rows:
        row = InventoryCsvRow(row=row_num)
        if "our_ref" in applied_map:
            row.our_ref = _cell(headers, cells, applied_map["our_ref"]) or None
            if row.our_ref is None:
                row.errors.append("our_ref is required")
        if "name" in applied_map:
            row.name = _cell(headers, cells, applied_map["name"]) or None
            if row.name is None:
                row.errors.append("name is required")
        if "category" in applied_map:
            row.category = _cell(headers, cells, applied_map["category"]) or None
            if row.category is None:
                row.errors.append("Category is required")
        if "retail_inc_vat" in applied_map:
            raw_retail = _cell(headers, cells, applied_map["retail_inc_vat"])
            if not raw_retail:
                row.errors.append("retail_inc_vat is required")
            else:
                try:
                    row.retail_inc_vat = _parse_money(raw_retail, "retail_inc_vat")
                except ValidationError as exc:
                    row.errors.append(exc.detail)
        if "barcode" in applied_map:
            row.barcode = _cell(headers, cells, applied_map["barcode"]) or None
        if "cost_zar" in applied_map:
            raw_cost = _cell(headers, cells, applied_map["cost_zar"])
            if raw_cost:
                try:
                    row.cost_zar = _parse_money(raw_cost, "cost_zar")
                except ValidationError as exc:
                    row.errors.append(exc.detail)
        if "carton_count" in applied_map:
            raw_cartons = _cell(headers, cells, applied_map["carton_count"])
            if not raw_cartons:
                row.carton_count = 1
            else:
                try:
                    row.carton_count = _parse_carton_count(raw_cartons)
                except ValidationError as exc:
                    row.errors.append(exc.detail)
        for message in row.errors:
            errors.append(CsvRowError(row=row_num, message=message))
        parsed_rows.append(row)

    return InventoryCsvParse(
        headers=headers,
        suggested_map=suggested_map,
        applied_map=applied_map,
        sample_row=_row_dict(headers, data_rows[0][1]),
        row_count=len(parsed_rows),
        rows=parsed_rows,
        errors=errors,
    )


def parse_soh_csv(content: bytes, map_json: Optional[str] = None) -> SohCsvParse:
    headers, data_rows = read_csv_table(content)
    suggested_map = suggest_column_map(headers, SOH_ALIASES)
    user_map = parse_column_map_json(map_json, SOH_FIELDS)
    applied_map, map_errors = resolve_applied_map(headers, suggested_map, user_map)
    errors = list(map_errors)
    errors.extend(_missing_column_errors(applied_map, SOH_REQUIRED))

    parsed_rows: list[SohCsvRow] = []
    for row_num, cells in data_rows:
        row = SohCsvRow(row=row_num)
        if "our_ref" in applied_map:
            row.our_ref = _cell(headers, cells, applied_map["our_ref"]) or None
            if row.our_ref is None:
                row.errors.append("our_ref is required")
        if "location" in applied_map:
            row.location = _cell(headers, cells, applied_map["location"]) or None
            if row.location is None:
                row.errors.append("location is required")
        if "qty" in applied_map:
            raw_qty = _cell(headers, cells, applied_map["qty"])
            if not raw_qty:
                row.errors.append("qty is required")
            else:
                try:
                    row.qty = _parse_qty(raw_qty)
                except ValidationError as exc:
                    row.errors.append(exc.detail)
        if "unit_cost_zar" in applied_map:
            raw_cost = _cell(headers, cells, applied_map["unit_cost_zar"])
            if raw_cost:
                try:
                    row.unit_cost_zar = _parse_money(raw_cost, "unit_cost_zar")
                except ValidationError as exc:
                    row.errors.append(exc.detail)
        for message in row.errors:
            errors.append(CsvRowError(row=row_num, message=message))
        parsed_rows.append(row)

    return SohCsvParse(
        headers=headers,
        suggested_map=suggested_map,
        applied_map=applied_map,
        sample_row=_row_dict(headers, data_rows[0][1]),
        row_count=len(parsed_rows),
        rows=parsed_rows,
        errors=errors,
    )
