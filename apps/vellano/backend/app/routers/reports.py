from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dependencies.auth import get_current_user_id, get_reports_service
from app.schemas.bank_import import (
    AgedReport,
    BalanceSheetReport,
    ProfitLossReport,
    Vat201Draft,
)
from app.services.reports import ReportsService
from app.services.reports_export import (
    build_aged_stock_csv,
    build_cash_summary_csv,
    build_journals_csv,
    build_sales_by_sku_csv,
    build_sales_vat_csv,
    build_stock_valuation_csv,
    build_trial_balance_csv,
)
from app.services.vat201_export import build_vat201_csv, build_vat201_pdf
from app.schemas.reports_books import (
    CashSummaryReport,
    JournalReport,
    TrialBalanceReport,
)
from app.schemas.reports_stock import (
    AgedStockReport,
    SalesBySkuReport,
    SalesVatReport,
    StockValuationReport,
)

reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@reports_router.get("/aged-ar", response_model=AgedReport)
async def aged_ar(
    as_of: datetime.date = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.aged_ar(as_of)


@reports_router.get("/aged-ap", response_model=AgedReport)
async def aged_ap(
    as_of: datetime.date = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.aged_ap(as_of)


@reports_router.get("/profit-loss", response_model=ProfitLossReport)
async def profit_loss(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.profit_loss(from_date, to_date)


@reports_router.get("/balance-sheet", response_model=BalanceSheetReport)
async def balance_sheet(
    as_of: datetime.date = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.balance_sheet(as_of)


@reports_router.get("/vat201", response_model=Vat201Draft)
async def vat201_draft(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.vat201_draft(from_date, to_date)


@reports_router.get("/vat201/csv")
async def vat201_csv(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    draft = await service.vat201_draft(from_date, to_date)
    content = build_vat201_csv(draft)
    filename = f"vat201-draft-{from_date.isoformat()}-to-{to_date.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/vat201/pdf")
async def vat201_pdf(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    draft = await service.vat201_draft(from_date, to_date)
    content = build_vat201_pdf(draft)
    filename = f"vat201-draft-{from_date.isoformat()}-to-{to_date.isoformat()}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/stock-valuation", response_model=StockValuationReport)
async def stock_valuation(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.stock_valuation()


@reports_router.get("/stock-valuation/csv")
async def stock_valuation_csv(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.stock_valuation()
    content = build_stock_valuation_csv(report)
    filename = f"stock-valuation-{datetime.date.today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/aged-stock", response_model=AgedStockReport)
async def aged_stock(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.aged_stock()


@reports_router.get("/aged-stock/csv")
async def aged_stock_csv(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.aged_stock()
    content = build_aged_stock_csv(report)
    filename = f"aged-stock-{datetime.date.today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/sales-by-sku", response_model=SalesBySkuReport)
async def sales_by_sku(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.sales_by_sku(from_date, to_date)


@reports_router.get("/sales-by-sku/csv")
async def sales_by_sku_csv(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.sales_by_sku(from_date, to_date)
    content = build_sales_by_sku_csv(report)
    filename = f"sales-by-sku-{from_date.isoformat()}-to-{to_date.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/sales-vat", response_model=SalesVatReport)
async def sales_vat(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.sales_vat(from_date, to_date)


@reports_router.get("/sales-vat/csv")
async def sales_vat_csv(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.sales_vat(from_date, to_date)
    content = build_sales_vat_csv(report)
    filename = f"sales-vat-{from_date.isoformat()}-to-{to_date.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/trial-balance", response_model=TrialBalanceReport)
async def trial_balance(
    as_of: datetime.date = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.trial_balance(as_of)


@reports_router.get("/trial-balance/csv")
async def trial_balance_csv(
    as_of: datetime.date = Query(...),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.trial_balance(as_of)
    content = build_trial_balance_csv(report)
    filename = f"trial-balance-{as_of.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/journals", response_model=JournalReport)
async def journal_report(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    source: Optional[str] = Query(default=None),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.journal_report(from_date, to_date, source)


@reports_router.get("/journals/csv")
async def journal_report_csv(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    source: Optional[str] = Query(default=None),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.journal_report(from_date, to_date, source)
    content = build_journals_csv(report)
    filename = f"journals-{from_date.isoformat()}-to-{to_date.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@reports_router.get("/cash-summary", response_model=CashSummaryReport)
async def cash_summary(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    return await service.cash_summary(from_date, to_date)


@reports_router.get("/cash-summary/csv")
async def cash_summary_csv(
    from_date: datetime.date = Query(..., alias="from"),
    to_date: datetime.date = Query(..., alias="to"),
    _: uuid.UUID = Depends(get_current_user_id),
    service: ReportsService = Depends(get_reports_service),
):
    report = await service.cash_summary(from_date, to_date)
    content = build_cash_summary_csv(report)
    filename = f"cash-summary-{from_date.isoformat()}-to-{to_date.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
