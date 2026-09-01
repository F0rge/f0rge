from __future__ import annotations

import datetime
import statistics
import uuid
from typing import Iterable, NamedTuple, Optional

from app.models.purchase_order import PurchaseOrder
from app.schemas.reports_lead import (
    SkuLeadTimeLine,
    SkuLeadTimesReport,
    SupplierLeadTimeLine,
    SupplierLeadTimesReport,
)

LAST_N = 3


class LeadSample(NamedTuple):
    received_at: datetime.datetime
    po_days: int
    water_days: Optional[int]


def calendar_lead_days(start: datetime.datetime, end: datetime.datetime) -> int:
    return (end.date() - start.date()).days


def median_days(values: list[int]) -> float:
    return float(statistics.median(values))


def percentile_90(values: list[int]) -> float:
    if len(values) == 1:
        return float(values[0])
    return float(statistics.quantiles(values, n=10, method="inclusive")[8])


def po_to_receive_days(po: PurchaseOrder) -> int:
    assert po.ordered_at is not None
    assert po.received_at is not None
    return calendar_lead_days(po.ordered_at, po.received_at)


def water_to_receive_days(po: PurchaseOrder) -> Optional[int]:
    if po.on_water_at is None or po.received_at is None:
        return None
    return calendar_lead_days(po.on_water_at, po.received_at)


def summarize_samples(
    samples: list[LeadSample],
) -> tuple[int, float, float, Optional[float], float]:
    days = [sample.po_days for sample in samples]
    newest = sorted(samples, key=lambda sample: sample.received_at, reverse=True)
    last_n = [sample.po_days for sample in newest[:LAST_N]]
    water = [sample.water_days for sample in samples if sample.water_days is not None]
    return (
        len(samples),
        median_days(days),
        median_days(last_n),
        median_days(water) if water else None,
        percentile_90(days),
    )


def _sample_from_po(po: PurchaseOrder) -> LeadSample:
    assert po.received_at is not None
    return LeadSample(
        received_at=po.received_at,
        po_days=po_to_receive_days(po),
        water_days=water_to_receive_days(po),
    )


def build_supplier_lead_times(orders: Iterable[PurchaseOrder]) -> SupplierLeadTimesReport:
    grouped: dict[uuid.UUID, list[LeadSample]] = {}
    names: dict[uuid.UUID, str] = {}
    for po in orders:
        grouped.setdefault(po.supplier_id, []).append(_sample_from_po(po))
        names[po.supplier_id] = po.supplier.name
    lines = []
    for supplier_id, samples in grouped.items():
        n, median, last_3, water_median, p90 = summarize_samples(samples)
        lines.append(
            SupplierLeadTimeLine(
                supplier_id=supplier_id,
                supplier_name=names[supplier_id],
                n=n,
                median_days=median,
                median_last_3_days=last_3,
                median_water_days=water_median,
                p90_days=p90,
            )
        )
    lines.sort(key=lambda line: (line.supplier_name.lower(), str(line.supplier_id)))
    return SupplierLeadTimesReport(lines=lines)


def build_sku_lead_times(orders: Iterable[PurchaseOrder]) -> SkuLeadTimesReport:
    grouped: dict[uuid.UUID, list[LeadSample]] = {}
    meta: dict[uuid.UUID, tuple[str, str, Optional[int]]] = {}
    for po in orders:
        sample = _sample_from_po(po)
        for line in po.lines:
            grouped.setdefault(line.sku_id, []).append(sample)
            meta[line.sku_id] = (line.sku.our_ref, line.sku.name, line.sku.lead_time_days)
    lines = []
    for sku_id, samples in grouped.items():
        our_ref, name, manual = meta[sku_id]
        n, median, last_3, water_median, p90 = summarize_samples(samples)
        lines.append(
            SkuLeadTimeLine(
                sku_id=sku_id,
                our_ref=our_ref,
                name=name,
                manual_lead_time_days=manual,
                n=n,
                median_days=median,
                median_last_3_days=last_3,
                median_water_days=water_median,
                p90_days=p90,
            )
        )
    lines.sort(key=lambda line: (line.our_ref, str(line.sku_id)))
    return SkuLeadTimesReport(lines=lines)
