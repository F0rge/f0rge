from __future__ import annotations

import csv
import io
from typing import Optional

from app.schemas.reports_books import (
    CashSummaryReport,
    JournalReport,
    TrialBalanceReport,
)
from app.schemas.reports_criticality import SkuCriticalityReport
from app.schemas.reports_lead import SkuLeadTimesReport, SupplierLeadTimesReport
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


def build_sku_criticality_csv(report: SkuCriticalityReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["from", report.from_date.isoformat(), "to", report.to_date.isoformat()])
    writer.writerow(
        [
            "sku_count_for_50pct",
            report.sku_count_for_50pct,
            "sku_count_for_80pct",
            report.sku_count_for_80pct,
            "top_sku_share_pct",
            f"{report.top_sku_share_pct:.2f}",
        ]
    )
    writer.writerow(
        [
            "sku_id",
            "our_ref",
            "name",
            "category",
            "qty",
            "value_zar",
            "share_pct",
            "cumulative_pct",
            "abc_class",
            "hits_50pct_band",
            "is_a",
        ]
    )
    for line in report.lines:
        writer.writerow(
            [
                str(line.sku_id),
                line.our_ref,
                line.name,
                line.category or "",
                line.qty,
                f"{line.value_zar:.2f}",
                f"{line.share_pct:.2f}",
                f"{line.cumulative_pct:.2f}",
                line.abc_class,
                line.hits_50pct_band,
                line.is_a,
            ]
        )
    writer.writerow([])
    writer.writerow(
        [
            "category",
            "qty",
            "value_zar",
            "share_pct",
            "cumulative_pct",
            "abc_class",
        ]
    )
    for line in report.categories:
        writer.writerow(
            [
                line.category,
                line.qty,
                f"{line.value_zar:.2f}",
                f"{line.share_pct:.2f}",
                f"{line.cumulative_pct:.2f}",
                line.abc_class,
            ]
        )
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


def _optional_days(value: Optional[float]) -> str:
    if value is None:
        return ""
    if value == int(value):
        return str(int(value))
    return str(value)


def build_supplier_lead_times_csv(report: SupplierLeadTimesReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "supplier_id",
            "supplier_name",
            "n",
            "median_days",
            "median_last_3_days",
            "median_water_days",
            "p90_days",
        ]
    )
    for line in report.lines:
        writer.writerow(
            [
                str(line.supplier_id),
                line.supplier_name,
                line.n,
                _optional_days(line.median_days),
                _optional_days(line.median_last_3_days),
                _optional_days(line.median_water_days),
                _optional_days(line.p90_days),
            ]
        )
    return buffer.getvalue().encode("utf-8")


def build_sku_lead_times_csv(report: SkuLeadTimesReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "sku_id",
            "our_ref",
            "name",
            "manual_lead_time_days",
            "n",
            "median_days",
            "median_last_3_days",
            "median_water_days",
            "p90_days",
        ]
    )
    for line in report.lines:
        writer.writerow(
            [
                str(line.sku_id),
                line.our_ref,
                line.name,
                "" if line.manual_lead_time_days is None else line.manual_lead_time_days,
                line.n,
                _optional_days(line.median_days),
                _optional_days(line.median_last_3_days),
                _optional_days(line.median_water_days),
                _optional_days(line.p90_days),
            ]
        )
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


def build_trial_balance_csv(report: TrialBalanceReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["as_of", report.as_of.isoformat()])
    writer.writerow(["code", "name", "debit_zar", "credit_zar"])
    for line in report.lines:
        writer.writerow(
            [
                line.code,
                line.name,
                f"{line.debit_zar:.2f}",
                f"{line.credit_zar:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["total_debit_zar", f"{report.total_debit_zar:.2f}"])
    writer.writerow(["total_credit_zar", f"{report.total_credit_zar:.2f}"])
    return buffer.getvalue().encode("utf-8")


def build_journals_csv(report: JournalReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["from", report.from_date.isoformat(), "to", report.to_date.isoformat()])
    writer.writerow(
        [
            "entry_date",
            "journal_number",
            "document_type",
            "source",
            "memo",
            "status",
            "account_code",
            "account_name",
            "debit_zar",
            "credit_zar",
        ]
    )
    for entry in report.entries:
        for line in entry.lines:
            writer.writerow(
                [
                    entry.entry_date.isoformat(),
                    entry.journal_number or "",
                    entry.document_type.value,
                    entry.source or "",
                    entry.memo or "",
                    entry.status.value,
                    line.account_code,
                    line.account_name,
                    f"{line.debit_zar:.2f}",
                    f"{line.credit_zar:.2f}",
                ]
            )
    return buffer.getvalue().encode("utf-8")


def build_cash_summary_csv(report: CashSummaryReport) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["from", report.from_date.isoformat(), "to", report.to_date.isoformat()])
    writer.writerow(["code", "name", "cash_in_zar", "cash_out_zar", "net_zar"])
    for account in report.accounts:
        writer.writerow(
            [
                account.code,
                account.name,
                f"{account.cash_in_zar:.2f}",
                f"{account.cash_out_zar:.2f}",
                f"{account.net_zar:.2f}",
            ]
        )
    writer.writerow([])
    writer.writerow(["total_cash_in_zar", f"{report.total_cash_in_zar:.2f}"])
    writer.writerow(["total_cash_out_zar", f"{report.total_cash_out_zar:.2f}"])
    writer.writerow(["total_net_zar", f"{report.total_net_zar:.2f}"])
    return buffer.getvalue().encode("utf-8")
