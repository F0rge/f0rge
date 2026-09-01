from __future__ import annotations

import datetime
import uuid

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
from app.services.vat201_export import build_vat201_csv, build_vat201_pdf

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
