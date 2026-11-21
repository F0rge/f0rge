from __future__ import annotations

import datetime
import hashlib
import json
from decimal import Decimal, InvalidOperation

from f0rge_core.exceptions import ValidationError
from pydantic import BaseModel

from app.schemas.record_workspace import WorkspaceFilter, WorkspaceQuery


def revision(row: BaseModel) -> str:
    return payload_hash(_canonical(row.model_dump(mode="python")))


def _canonical(value):
    """Database numeric scale and relationship load order are not edits."""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f") if value else "0"
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [_canonical(item) for item in value]
        if items and all(
            isinstance(item, dict) and ("id" in item or "sku_id" in item) for item in items
        ):
            items.sort(key=lambda item: str(item.get("id", item.get("sku_id"))))
        return items
    return value


def payload_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def archived(row: BaseModel, field: str) -> bool:
    if not field:
        return False
    value = bool(getattr(row, field, False))
    return not value if field == "is_active" else value


def label(row: BaseModel) -> str:
    return str(
        getattr(row, "name", None)
        or getattr(row, "display_name", None)
        or getattr(row, "invoice_number", None)
        or getattr(row, "quote_number", None)
        or getattr(row, "bill_number", None)
        or getattr(row, "email", None)
        or row.id
    )


def scalar(value, kind: str):
    if value is None:
        return None
    try:
        if kind == "number":
            result = Decimal(str(value))
            if not result.is_finite():
                raise ValueError
            return result
        if kind == "boolean":
            if value is True or value == "true":
                return True
            if value is False or value == "false":
                return False
            raise ValueError
        if kind == "date":
            if isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()[:10]
            return datetime.date.fromisoformat(str(value)).isoformat()
        if isinstance(value, list):
            return " ".join(str(part) for part in value).casefold()
        return str(getattr(value, "value", value)).casefold()
    except (ValueError, InvalidOperation, TypeError) as exc:
        raise ValidationError(f"Invalid {kind} filter value") from exc


def validate_filters(query: WorkspaceQuery, fields: dict[str, str]) -> None:
    for condition in query.filters:
        if condition.field not in fields:
            raise ValidationError(f"Unsupported filter field: {condition.field}")
        kind = fields[condition.field]
        if condition.operator in {"gt", "gte", "lt", "lte"} and kind not in {"number", "date"}:
            raise ValidationError("Ranges require a number or date field")
        if condition.operator == "contains" and kind != "text":
            raise ValidationError("Contains requires a text field")
        if condition.operator not in {"empty", "not_empty"}:
            if condition.value is None:
                raise ValidationError("A filter value is required")
            scalar(condition.value, kind)
    if query.sort and query.sort.field not in fields:
        raise ValidationError(f"Unsupported sort field: {query.sort.field}")


def matches(row: BaseModel, condition: WorkspaceFilter, fields: dict[str, str]) -> bool:
    value = getattr(row, condition.field, None)
    empty = value is None or value == "" or value == []
    if condition.operator == "empty":
        return empty
    if condition.operator == "not_empty":
        return not empty
    if empty:
        return condition.operator == "ne"
    left = scalar(value, fields[condition.field])
    right = scalar(condition.value, fields[condition.field])
    if condition.operator == "eq":
        return left == right
    if condition.operator == "ne":
        return left != right
    if condition.operator == "contains":
        return right in left
    if condition.operator == "gt":
        return left > right
    if condition.operator == "gte":
        return left >= right
    if condition.operator == "lt":
        return left < right
    return left <= right


def filter_rows(
    rows: list[BaseModel], query: WorkspaceQuery, fields: dict[str, str]
) -> list[BaseModel]:
    validate_filters(query, fields)
    q = query.q.strip().casefold()
    result = []
    for row in rows:
        if q and not any(
            q in str(getattr(row, field, "") or "").casefold()
            for field, kind in fields.items()
            if kind == "text"
        ):
            continue
        values = [matches(row, condition, fields) for condition in query.filters]
        if values and not (all(values) if query.match == "all" else any(values)):
            continue
        result.append(row)
    result.sort(key=lambda row: str(row.id))
    if query.sort:
        field = query.sort.field
        result.sort(
            key=lambda row: (
                getattr(row, field, None) is None,
                scalar(getattr(row, field), fields[field])
                if getattr(row, field, None) is not None
                else "",
            ),
            reverse=query.sort.direction == "desc",
        )
    else:
        result.sort(key=lambda row: label(row).casefold())
    return result
