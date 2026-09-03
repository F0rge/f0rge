from __future__ import annotations

import datetime
import enum
from decimal import Decimal
from typing import Any, Optional, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError as PydanticValidationError
from pydantic.fields import FieldInfo

from app.nia.actions import NiaAction, SECRET_ARG_KEYS

NEEDS_FIELDS_KIND = "needs_fields"
FIELDS_ASSISTANT_TEXT = "Fill in the required fields to continue."
FIELDS_SOURCE = "fields"

# Model args Nia often names loosely (barcode vs our_barcode).
FIELD_ALIASES: dict[str, str] = {
    "barcode": "our_barcode",
    "sku": "our_ref",
    "sku_code": "our_ref",
    "ref": "our_ref",
}


def canonical_field_values(supplied: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Copy supplied keys and map common aliases onto the Pydantic field ids."""
    values: dict[str, Any] = dict(supplied or {})
    for key, value in list(values.items()):
        canonical = FIELD_ALIASES.get(key)
        if canonical and canonical not in values:
            values[canonical] = value
    return values


_FIELD_LABELS: dict[str, str] = {
    "our_ref": "Our ref",
    "our_barcode": "Our barcode",
    "name": "Name",
    "design": "Design",
    "fabric": "Fabric",
    "supplier_ref": "Supplier ref",
    "category": "Category",
    "sku_id": "SKU",
    "customer_id": "Customer",
    "issue_date": "Issue date",
    "lines": "Lines",
    "from_location_id": "From location",
    "to_location_id": "To location",
    "transfer_id": "Transfer",
    "invoice_id": "Invoice",
    "journal_id": "Journal",
    "account_id": "Account",
    "location_id": "Location",
    "unit_cost_zar": "Unit cost (ZAR)",
    "qty": "Quantity",
    "description": "Description",
    "unit_ex_vat": "Unit ex VAT",
}

_SKIP_OPTIONAL_PREFIXES: tuple[str, ...] = ("opening_",)


def _unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    if origin is Union:
        args = [item for item in get_args(annotation) if item is not type(None)]
        if len(args) == 1:
            return args[0], True
        if args:
            return args[0], True
    return annotation, False


def _is_model_type(value: Any) -> bool:
    try:
        return isinstance(value, type) and issubclass(value, BaseModel)
    except TypeError:
        return False


def _is_enum_type(value: Any) -> bool:
    try:
        return isinstance(value, type) and issubclass(value, enum.Enum)
    except TypeError:
        return False


def _field_type(annotation: Any) -> str:
    inner, _optional = _unwrap_optional(annotation)
    origin = get_origin(inner)
    if inner is bool:
        return "boolean"
    if inner in (int, float, Decimal):
        return "number"
    if inner is datetime.date:
        return "date"
    if origin is list or origin is dict or _is_model_type(inner):
        return "json"
    if origin is not None and getattr(origin, "__name__", "") == "Literal":
        return "select"
    if _is_enum_type(inner):
        return "select"
    return "text"


def _field_options(annotation: Any) -> Optional[list[dict[str, str]]]:
    inner, _optional = _unwrap_optional(annotation)
    origin = get_origin(inner)
    if origin is not None and getattr(origin, "__name__", "") == "Literal":
        options: list[dict[str, str]] = []
        for item in get_args(inner):
            text = str(item)
            options.append({"id": text, "text": text})
        return options or None
    if _is_enum_type(inner):
        return [{"id": str(item.value), "text": str(item.value)} for item in inner]
    if inner is bool:
        return [{"id": "true", "text": "Yes"}, {"id": "false", "text": "No"}]
    return None


def _label_for(field_id: str) -> str:
    if field_id in _FIELD_LABELS:
        return _FIELD_LABELS[field_id]
    return field_id.replace("_", " ").capitalize()


def _errors_by_field(exc: Optional[PydanticValidationError]) -> dict[str, str]:
    if exc is None:
        return {}
    grouped: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc") or ()
        if not loc:
            continue
        key = str(loc[0])
        grouped.setdefault(key, str(err.get("msg") or "invalid"))
    return grouped


def _stringify_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value)
    return str(value)


def _should_include_optional(field_id: str, info: FieldInfo, field_type: str) -> bool:
    if field_id in SECRET_ARG_KEYS:
        return False
    if any(field_id.startswith(prefix) for prefix in _SKIP_OPTIONAL_PREFIXES):
        return False
    if field_type == "json":
        return False
    return True


def fields_from_model(
    model: type[BaseModel],
    supplied: Optional[dict[str, Any]] = None,
    exc: Optional[PydanticValidationError] = None,
) -> list[dict[str, Any]]:
    """Describe form fields from a Pydantic args model."""
    values = canonical_field_values(supplied)
    errors = _errors_by_field(exc)
    required_rows: list[dict[str, Any]] = []
    optional_rows: list[dict[str, Any]] = []

    for field_id, info in model.model_fields.items():
        if field_id in SECRET_ARG_KEYS:
            continue
        required = info.is_required()
        field_type = _field_type(info.annotation)
        if not required and not _should_include_optional(field_id, info, field_type):
            if field_id not in values and field_id not in errors:
                continue
        row: dict[str, Any] = {
            "id": field_id,
            "label": _label_for(field_id),
            "type": field_type,
            "required": required,
        }
        options = _field_options(info.annotation)
        if options:
            row["options"] = options
        if field_id in values:
            rendered = _stringify_value(values[field_id])
            if rendered is not None:
                row["value"] = rendered
        if field_id in errors:
            row["error"] = errors[field_id]
        if required:
            required_rows.append(row)
        else:
            optional_rows.append(row)

    if len(optional_rows) > 8:
        optional_rows = [row for row in optional_rows if row["id"] in values or row["id"] in errors]
    return required_rows + optional_rows


def build_needs_fields_payload(
    action: NiaAction,
    supplied: Optional[dict[str, Any]] = None,
    exc: Optional[PydanticValidationError] = None,
) -> dict[str, Any]:
    values = canonical_field_values(supplied)
    return {
        "kind": NEEDS_FIELDS_KIND,
        "action_id": action.id,
        "title": action.title,
        "body": FIELDS_ASSISTANT_TEXT,
        "fields": fields_from_model(action.args_model, values, exc),
        "values": values,
        "source": FIELDS_SOURCE,
    }


def should_emit_fields_form(action: NiaAction) -> bool:
    """Writes with missing/invalid args become a form; reads stay chat."""
    return action.write
