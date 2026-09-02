from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.sku import Sku
from app.models.tax_invoice import InvoiceLine, TaxInvoice
from app.services.inventory import InventoryService
from app.services.reports import ReportsService

CANVAS_PATH = "/canvas"
CANVAS_SPEC_KIND = "canvas_spec"
CANVAS_CLEARED_KIND = "canvas_cleared"
CHART_TYPES = frozenset({"bar", "line", "table", "metric"})

DEFAULT_SALES_BY_SKU_TOP_N = 8


def empty_canvas_spec(title: str = "") -> dict[str, Any]:
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": title,
        "components": [],
    }


def canvas_cleared_payload() -> dict[str, Any]:
    return {
        "kind": CANVAS_CLEARED_KIND,
        "path": CANVAS_PATH,
        "cleared_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }


def is_canvas_spec(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == CANVAS_SPEC_KIND


def is_canvas_cleared(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == CANVAS_CLEARED_KIND


def spec_from_thread_payloads(payloads: list[Any]) -> dict[str, Any]:
    """Newest canvas event wins. A later clear wipes older specs."""
    for payload in reversed(payloads):
        if is_canvas_cleared(payload):
            return empty_canvas_spec()
        if is_canvas_spec(payload):
            parsed = parse_canvas_spec(payload)
            if parsed is not None:
                return parsed
    return empty_canvas_spec()


def _is_record(value: Any) -> bool:
    return isinstance(value, dict)


def _parse_series(value: Any) -> Optional[list[dict[str, Any]]]:
    if not isinstance(value, list):
        return None
    series: list[dict[str, Any]] = []
    for entry in value:
        if not _is_record(entry) or not isinstance(entry.get("name"), str):
            return None
        raw_values = entry.get("values")
        if not isinstance(raw_values, list):
            return None
        values: list[float] = []
        for raw in raw_values:
            if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal)):
                return None
            values.append(float(raw))
        series.append({"name": entry["name"], "values": values})
    return series


def parse_canvas_component(raw: Any) -> Optional[dict[str, Any]]:
    if not _is_record(raw) or raw.get("type") not in CHART_TYPES:
        return None
    component_type = raw["type"]
    if component_type in {"bar", "line"}:
        if not isinstance(raw.get("id"), str) or not isinstance(raw.get("title"), str):
            return None
        if not isinstance(raw.get("categories"), list):
            return None
        categories = [item for item in raw["categories"] if isinstance(item, str)]
        if len(categories) != len(raw["categories"]):
            return None
        series = _parse_series(raw.get("series"))
        if series is None:
            return None
        return {
            "type": component_type,
            "id": raw["id"],
            "title": raw["title"],
            "categories": categories,
            "series": series,
        }
    if component_type == "table":
        if not isinstance(raw.get("id"), str) or not isinstance(raw.get("title"), str):
            return None
        if not isinstance(raw.get("headers"), list) or not isinstance(raw.get("rows"), list):
            return None
        headers = [item for item in raw["headers"] if isinstance(item, str)]
        if len(headers) != len(raw["headers"]):
            return None
        rows: list[list[str]] = []
        for row in raw["rows"]:
            if not isinstance(row, list):
                return None
            cells = [cell for cell in row if isinstance(cell, str)]
            if len(cells) != len(row):
                return None
            rows.append(cells)
        return {
            "type": "table",
            "id": raw["id"],
            "title": raw["title"],
            "headers": headers,
            "rows": rows,
        }
    if component_type == "metric":
        if (
            not isinstance(raw.get("id"), str)
            or not isinstance(raw.get("label"), str)
            or not isinstance(raw.get("value"), str)
        ):
            return None
        return {
            "type": "metric",
            "id": raw["id"],
            "label": raw["label"],
            "value": raw["value"],
        }
    return None


def parse_canvas_spec(raw: Any) -> Optional[dict[str, Any]]:
    if not is_canvas_spec(raw):
        return None
    if raw.get("path") != CANVAS_PATH or not isinstance(raw.get("title"), str):
        return None
    if not isinstance(raw.get("components"), list):
        return None
    components: list[dict[str, Any]] = []
    for entry in raw["components"]:
        component = parse_canvas_component(entry)
        if component is None:
            return None
        components.append(component)
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": raw["title"],
        "components": components,
    }


def set_canvas_spec(title: str, components: list[Any]) -> Optional[dict[str, Any]]:
    parsed_components: list[dict[str, Any]] = []
    for entry in components:
        component = parse_canvas_component(entry)
        if component is None:
            return None
        parsed_components.append(component)
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": title,
        "components": parsed_components,
    }


def add_canvas_component(spec: dict[str, Any], component: Any) -> Optional[dict[str, Any]]:
    parsed = parse_canvas_component(component)
    if parsed is None:
        return None
    current = parse_canvas_spec(spec) or empty_canvas_spec(str(spec.get("title") or ""))
    components = [entry for entry in current["components"] if entry.get("id") != parsed["id"]]
    components.append(parsed)
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": current["title"],
        "components": components,
    }


def remove_canvas_component(spec: dict[str, Any], component_id: str) -> dict[str, Any]:
    current = parse_canvas_spec(spec) or empty_canvas_spec(str(spec.get("title") or ""))
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": current["title"],
        "components": [entry for entry in current["components"] if entry.get("id") != component_id],
    }


def set_canvas_title(spec: dict[str, Any], title: str) -> dict[str, Any]:
    current = parse_canvas_spec(spec) or empty_canvas_spec(title)
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": title,
        "components": current["components"],
    }


def merge_canvas_mode(
    current: dict[str, Any],
    incoming: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    parsed_incoming = parse_canvas_spec(incoming)
    if parsed_incoming is None:
        return parse_canvas_spec(current) or empty_canvas_spec()
    if normalize_canvas_mode(mode) != "add":
        return parsed_incoming
    merged = parse_canvas_spec(current) or empty_canvas_spec(parsed_incoming["title"])
    by_id = {entry["id"]: entry for entry in merged["components"]}
    for component in parsed_incoming["components"]:
        by_id[component["id"]] = component
    title = merged["title"] or parsed_incoming["title"]
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": title,
        "components": list(by_id.values()),
    }


def normalize_canvas_mode(mode: Optional[str]) -> str:
    value = (mode or "replace").strip().lower()
    if value in {"add", "append", "underneath"}:
        return "add"
    return "replace"


def _month_bounds(today: datetime.date) -> tuple[datetime.date, datetime.date]:
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = datetime.date(today.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        month_end = datetime.date(today.year, today.month + 1, 1) - datetime.timedelta(days=1)
    return month_start, month_end


def _classify_bucket(line: InvoiceLine, sku: Optional[Sku]) -> Optional[str]:
    description = (line.description or "").lower()
    if "dining" in description:
        return "dining"

    if sku is not None:
        category = (sku.category or "").lower()
        name = (sku.name or "").lower()
        our_ref = (sku.our_ref or "").lower()
        if "dining" in category or "dining" in name or "dining" in our_ref:
            return "dining"
        if category == "seating":
            return "sofas"
        if "sofa" in category or "sofa" in name or "sofa" in our_ref:
            return "sofas"

    if "sofa" in description:
        return "sofas"
    return None


def _zar_cell(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _build_dining_vs_sofas_spec(dining_total: float, sofas_total: float) -> dict[str, Any]:
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": "Dining vs sofas this month",
        "components": [
            {
                "type": "bar",
                "id": "dining-vs-sofas",
                "title": "Sales this month (ZAR inc VAT)",
                "categories": ["Dining", "Sofas"],
                "series": [{"name": "Sales", "values": [dining_total, sofas_total]}],
            }
        ],
    }


async def build_dining_vs_sofas_canvas_spec(db: AsyncSession) -> dict[str, Any]:
    today = datetime.date.today()
    month_start, month_end = _month_bounds(today)

    stmt = (
        select(InvoiceLine, Sku)
        .join(TaxInvoice, InvoiceLine.invoice_id == TaxInvoice.id)
        .outerjoin(Sku, InvoiceLine.sku_id == Sku.id)
        .where(
            TaxInvoice.issue_date >= month_start,
            TaxInvoice.issue_date <= month_end,
        )
    )
    rows = (await db.execute(stmt)).all()

    dining_total = Decimal(0)
    sofas_total = Decimal(0)
    for line, sku in rows:
        bucket = _classify_bucket(line, sku)
        if bucket == "dining":
            dining_total += line.inc_vat
        elif bucket == "sofas":
            sofas_total += line.inc_vat

    return _build_dining_vs_sofas_spec(float(dining_total), float(sofas_total))


async def build_overdue_invoices_canvas_spec(db: AsyncSession) -> dict[str, Any]:
    today = datetime.date.today()
    overdue_cutoff = today - datetime.timedelta(days=30)
    balance = TaxInvoice.total_inc_vat - TaxInvoice.amount_paid
    stmt = (
        select(TaxInvoice, Customer.name)
        .join(Customer, TaxInvoice.customer_id == Customer.id)
        .where(
            and_(
                balance > 0,
                TaxInvoice.issue_date <= overdue_cutoff,
            )
        )
        .order_by(TaxInvoice.issue_date, TaxInvoice.invoice_number)
    )
    rows = (await db.execute(stmt)).all()
    table_rows = [
        [
            invoice.invoice_number,
            customer_name,
            invoice.issue_date.isoformat(),
            _zar_cell(invoice.total_inc_vat - invoice.amount_paid),
        ]
        for invoice, customer_name in rows
    ]
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": "Overdue invoices",
        "components": [
            {
                "type": "table",
                "id": "overdue-invoices",
                "title": "Overdue invoices (30-day terms)",
                "headers": ["Invoice", "Customer", "Issue date", "Remaining (ZAR)"],
                "rows": table_rows,
            }
        ],
    }


async def build_sales_by_sku_canvas_spec(
    db: AsyncSession,
    top_n: int = DEFAULT_SALES_BY_SKU_TOP_N,
) -> dict[str, Any]:
    today = datetime.date.today()
    month_start, month_end = _month_bounds(today)
    limit = max(1, min(int(top_n), 20))
    report = await ReportsService(db).sales_by_sku(month_start, month_end)
    ranked = sorted(report.lines, key=lambda line: line.inc_vat_zar, reverse=True)[:limit]
    categories = [line.our_ref for line in ranked]
    values = [float(line.inc_vat_zar) for line in ranked]
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": "Sales by SKU this month",
        "components": [
            {
                "type": "bar",
                "id": "sales-by-sku",
                "title": f"Top {limit} SKUs this month (ZAR inc VAT)",
                "categories": categories,
                "series": [{"name": "Sales", "values": values}],
            }
        ],
    }


async def build_stock_on_hand_canvas_spec(
    db: AsyncSession,
    sku_ref: str,
    location_name: str,
    user_id: uuid.UUID,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    payload = await InventoryService(db).get_at_location(sku_ref, location_name, user_id)
    error = payload.get("error")
    if error:
        return None, str(error)
    our_ref = str(payload.get("our_ref") or sku_ref)
    location = str(payload.get("location") or location_name)
    on_hand = str(payload.get("on_hand") if payload.get("on_hand") is not None else "")
    row = [our_ref, location, on_hand]
    if "unit_cost_zar" in payload:
        cost = payload.get("unit_cost_zar")
        row.append("" if cost is None else str(cost))
        headers = ["SKU", "Location", "On hand", "Unit cost (ZAR)"]
    else:
        headers = ["SKU", "Location", "On hand"]
    spec = {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": f"Stock on hand — {our_ref}",
        "components": [
            {
                "type": "table",
                "id": f"stock-on-hand-{our_ref}-{location}".lower().replace(" ", "-"),
                "title": f"Stock on hand — {our_ref} at {location}",
                "headers": headers,
                "rows": [row],
            }
        ],
    }
    return spec, None


async def build_aged_ar_canvas_spec(db: AsyncSession) -> dict[str, Any]:
    today = datetime.date.today()
    report = await ReportsService(db).aged_ar(today)
    categories = [bucket.label for bucket in report.buckets]
    values = [float(bucket.amount_zar) for bucket in report.buckets]
    return {
        "kind": CANVAS_SPEC_KIND,
        "path": CANVAS_PATH,
        "title": "Aged receivables",
        "components": [
            {
                "type": "bar",
                "id": "aged-ar",
                "title": f"Aged AR as of {today.isoformat()} (ZAR)",
                "categories": categories,
                "series": [{"name": "Outstanding", "values": values}],
            }
        ],
    }
