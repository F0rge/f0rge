from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_vat201_period_service,
    require_books_mutate,
    require_owner,
)
from app.schemas.vat201_period import (
    Vat201PeriodCreate,
    Vat201PeriodDetailResponse,
    Vat201PeriodReopen,
    Vat201PeriodResponse,
)
from app.services.vat201_periods import Vat201PeriodService

vat201_periods_router = APIRouter(prefix="/api/v1/vat201/periods", tags=["vat201"])


@vat201_periods_router.get("", response_model=list[Vat201PeriodResponse])
async def list_periods(
    _: uuid.UUID = Depends(get_current_user_id),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
):
    return await service.list()


@vat201_periods_router.post(
    "", response_model=Vat201PeriodDetailResponse, status_code=status.HTTP_201_CREATED
)
async def create_period(
    body: Vat201PeriodCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
):
    return await service.create(body)


@vat201_periods_router.get("/{period_id}", response_model=Vat201PeriodDetailResponse)
async def get_period(
    period_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
):
    return await service.get(period_id)


@vat201_periods_router.post("/{period_id}/lock", response_model=Vat201PeriodDetailResponse)
async def lock_period(
    period_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
):
    return await service.lock(period_id, user_id)


@vat201_periods_router.post("/{period_id}/reopen", response_model=Vat201PeriodDetailResponse)
async def reopen_period(
    period_id: uuid.UUID,
    body: Vat201PeriodReopen,
    user_id: uuid.UUID = Depends(require_owner),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
):
    return await service.reopen(period_id, user_id, body)


@vat201_periods_router.get("/{period_id}/csv")
async def period_csv(
    period_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
) -> Response:
    return await service.serve_csv(period_id)


@vat201_periods_router.get("/{period_id}/pdf")
async def period_pdf(
    period_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: Vat201PeriodService = Depends(get_vat201_period_service),
) -> Response:
    return await service.serve_pdf(period_id)
