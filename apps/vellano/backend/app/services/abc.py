from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import NamedTuple, Optional

from dateutil.relativedelta import relativedelta

A_THRESHOLD = Decimal("0.80")
B_THRESHOLD = Decimal("0.95")
FIFTY_THRESHOLD = Decimal("0.50")
HUNDRED = Decimal("100")
UNCATEGORISED = "Uncategorised"


class AbcSkuInput(NamedTuple):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    category: Optional[str]
    qty: int
    value_zar: Decimal


class AbcRankedLine(NamedTuple):
    sku_id: uuid.UUID
    our_ref: str
    name: str
    category: Optional[str]
    qty: int
    value_zar: Decimal
    share_pct: Decimal
    cumulative_pct: Decimal
    abc_class: str
    hits_50pct_band: bool
    is_a: bool


class AbcCategoryLine(NamedTuple):
    category: str
    qty: int
    value_zar: Decimal
    share_pct: Decimal
    cumulative_pct: Decimal
    abc_class: str


class AbcReportResult(NamedTuple):
    sku_count_for_50pct: int
    sku_count_for_80pct: int
    top_sku_share_pct: Decimal
    lines: list[AbcRankedLine]
    categories: list[AbcCategoryLine]


def default_report_date_range(
    today: Optional[datetime.date] = None,
) -> tuple[datetime.date, datetime.date]:
    end = today or datetime.date.today()
    start = end - relativedelta(months=12)
    return start, end


def resolve_report_date_range(
    from_date: Optional[datetime.date],
    to_date: Optional[datetime.date],
    *,
    today: Optional[datetime.date] = None,
) -> tuple[datetime.date, datetime.date]:
    if from_date is None and to_date is None:
        return default_report_date_range(today)
    if from_date is None or to_date is None:
        raise ValueError("from and to must both be provided or both omitted")
    if from_date > to_date:
        raise ValueError("from_date must be on or before to_date")
    return from_date, to_date


def _pct_share(part: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal(0)
    return (part / total * HUNDRED).quantize(Decimal("0.01"))


def _abc_class(cumulative_fraction: Decimal) -> str:
    if cumulative_fraction <= A_THRESHOLD:
        return "A"
    if cumulative_fraction <= B_THRESHOLD:
        return "B"
    return "C"


def _rank_value_rows(
    rows: list[tuple[Decimal, int, tuple]],
) -> tuple[list, int, int, Decimal]:
    """Rank pre-sorted (value, qty, payload) rows by descending value."""
    total_value = sum((value for value, _, _ in rows), Decimal(0))
    if not rows:
        return [], 0, 0, Decimal(0)

    ranked: list = []
    cumulative_fraction = Decimal(0)
    sku_count_for_50pct = 0
    sku_count_for_80pct = 0
    hits_50_assigned = False
    top_share = _pct_share(rows[0][0], total_value)

    for index, (value, qty, payload) in enumerate(rows, start=1):
        share_fraction = value / total_value if total_value > 0 else Decimal(0)
        cumulative_fraction += share_fraction
        share_pct = _pct_share(value, total_value)
        cumulative_pct = (cumulative_fraction * HUNDRED).quantize(Decimal("0.01"))
        abc_class = _abc_class(cumulative_fraction)
        hits_50pct_band = False
        if not hits_50_assigned and cumulative_fraction >= FIFTY_THRESHOLD:
            hits_50pct_band = True
            hits_50_assigned = True
        if sku_count_for_50pct == 0 and cumulative_fraction >= FIFTY_THRESHOLD:
            sku_count_for_50pct = index
        if sku_count_for_80pct == 0 and cumulative_fraction >= A_THRESHOLD:
            sku_count_for_80pct = index
        ranked.append(
            (
                share_pct,
                cumulative_pct,
                abc_class,
                hits_50pct_band,
                qty,
                value,
                payload,
            )
        )

    return ranked, sku_count_for_50pct, sku_count_for_80pct, top_share


def build_abc_report(rows: list[AbcSkuInput]) -> AbcReportResult:
    sorted_rows = sorted(rows, key=lambda row: row.value_zar, reverse=True)
    sku_payloads = [(row.value_zar, row.qty, row) for row in sorted_rows if row.value_zar > 0]
    ranked, count_50, count_80, top_share = _rank_value_rows(sku_payloads)

    lines: list[AbcRankedLine] = []
    for share_pct, cumulative_pct, abc_class, hits_50, qty, value, row in ranked:
        lines.append(
            AbcRankedLine(
                sku_id=row.sku_id,
                our_ref=row.our_ref,
                name=row.name,
                category=row.category,
                qty=qty,
                value_zar=value,
                share_pct=share_pct,
                cumulative_pct=cumulative_pct,
                abc_class=abc_class,
                hits_50pct_band=hits_50,
                is_a=abc_class == "A",
            )
        )

    category_qty: dict[str, int] = {}
    category_value: dict[str, Decimal] = {}
    for row in sorted_rows:
        if row.value_zar <= 0:
            continue
        label = row.category if row.category else UNCATEGORISED
        category_qty[label] = category_qty.get(label, 0) + row.qty
        category_value[label] = category_value.get(label, 0) + row.value_zar

    category_rows = sorted(
        ((category_value[label], category_qty[label], label) for label in category_value),
        key=lambda item: item[0],
        reverse=True,
    )
    cat_ranked, _, _, _ = _rank_value_rows(
        [(value, qty, label) for value, qty, label in category_rows]
    )

    categories: list[AbcCategoryLine] = []
    for share_pct, cumulative_pct, abc_class, _, qty, value, label in cat_ranked:
        categories.append(
            AbcCategoryLine(
                category=label,
                qty=qty,
                value_zar=value,
                share_pct=share_pct,
                cumulative_pct=cumulative_pct,
                abc_class=abc_class,
            )
        )

    return AbcReportResult(
        sku_count_for_50pct=count_50,
        sku_count_for_80pct=count_80,
        top_sku_share_pct=top_share,
        lines=lines,
        categories=categories,
    )
