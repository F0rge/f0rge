from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sku import Sku
from app.models.tax_invoice import InvoiceLine, TaxInvoice


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


def _build_canvas_spec(dining_total: float, sofas_total: float) -> dict[str, Any]:
    return {
        "kind": "canvas_spec",
        "path": "/canvas",
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

    return _build_canvas_spec(float(dining_total), float(sofas_total))
