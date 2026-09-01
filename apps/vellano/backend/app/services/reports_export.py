from __future__ import annotations

import csv
import io

from app.schemas.reports_stock import (
    AgedStockReport,
    SalesBySkuReport,
    SalesVatReport,
    StockValuationReport,
)


def build_stock_valuation_csv(report: StockValuationReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "location_id",
            "location_name",
            "sku_id",
            "our_ref",
            "name",
            "on_hand",
            "unit_cost_zar",
            "value_zar",
        ]
    )
    for line in report.lines:
        writer.writerow(
            [
                str(line.location_id),
                line.location_name,
                str(line.sku_id),
                line.our_ref,
                line.name,
                line.on_hand,
                f"{line.unit_cost_zar:.4f}" if line.unit_cost_zar is not None else "",
                f"{line.value_zar:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["total_on_hand", report.total_on_hand])
    writer.writerow(["total_value_zar", f"{report.total_value_zar:.2f}"])
    return buffer.getvalue().encode("utf-8")


def build_aged_stock_csv(report: AgedStockReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "bucket",
            "sku_id",
            "our_ref",
            "name",
            "location_id",
            "location_name",
            "on_hand",
            "value_zar",
            "days",
        ]
    )
    for bucket in report.buckets:
        for line in bucket.lines:
            writer.writerow(
                [
                    line.bucket,
                    str(line.sku_id),
                    line.our_ref,
                    line.name,
                    str(line.location_id),
                    line.location_name,
                    line.on_hand,
                    f"{line.value_zar:.2f}",
                    line.days,
                ]
            )
    writer.writerow([])
    writer.writerow(["total_qty", report.total_qty])
    writer.writerow(["total_value_zar", f"{report.total_value_zar:.2f}"])
    return buffer.getvalue().encode("utf-8")


def build_sales_by_sku_csv(report: SalesBySkuReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["from", report.from_date.isoformat(), "to", report.to_date.isoformat()])
    writer.writerow(["sku_id", "our_ref", "name", "qty", "ex_vat_zar", "inc_vat_zar"])
    for line in report.lines:
        writer.writerow(
            [
                str(line.sku_id),
                line.our_ref,
                line.name,
                line.qty,
                f"{line.ex_vat_zar:.2f}",
                f"{line.inc_vat_zar:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["total_qty", report.total_qty])
    writer.writerow(["total_ex_vat_zar", f"{report.total_ex_vat_zar:.2f}"])
    writer.writerow(["total_inc_vat_zar", f"{report.total_inc_vat_zar:.2f}"])
    return buffer.getvalue().encode("utf-8")


def build_sales_vat_csv(report: SalesVatReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["from", report.from_date.isoformat(), "to", report.to_date.isoformat()])
    writer.writerow(["field", "value"])
    writer.writerow(["invoice_count", report.invoice_count])
    writer.writerow(["subtotal_ex_vat", f"{report.subtotal_ex_vat:.2f}"])
    writer.writerow(["vat_amount", f"{report.vat_amount:.2f}"])
    writer.writerow(["total_inc_vat", f"{report.total_inc_vat:.2f}"])
    writer.writerow(["amount_paid", f"{report.amount_paid:.2f}"])
    return buffer.getvalue().encode("utf-8")
