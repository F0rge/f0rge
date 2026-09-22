from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_books_period_service,
    get_current_user_id,
    require_books_mutate,
    require_owner,
)
from app.schemas.books_period import (
    BooksPeriodCreate,
    BooksPeriodReopen,
    BooksPeriodResponse,
)
from app.services.books_periods import BooksPeriodService

books_periods_router = APIRouter(prefix="/api/v1/books-periods", tags=["books-periods"])


@books_periods_router.get("", response_model=list[BooksPeriodResponse])
async def list_books_periods(
    _: uuid.UUID = Depends(get_current_user_id),
    service: BooksPeriodService = Depends(get_books_period_service),
) -> list[BooksPeriodResponse]:
    return await service.list()


@books_periods_router.post(
    "",
    response_model=BooksPeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_books_period(
    body: BooksPeriodCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BooksPeriodService = Depends(get_books_period_service),
) -> BooksPeriodResponse:
    return await service.create(body)


@books_periods_router.get("/{period_id}", response_model=BooksPeriodResponse)
async def get_books_period(
    period_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BooksPeriodService = Depends(get_books_period_service),
) -> BooksPeriodResponse:
    return await service.get(period_id)


@books_periods_router.post("/{period_id}/lock", response_model=BooksPeriodResponse)
async def lock_books_period(
    period_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: BooksPeriodService = Depends(get_books_period_service),
) -> BooksPeriodResponse:
    return await service.lock(period_id, user_id)


@books_periods_router.post("/{period_id}/reopen", response_model=BooksPeriodResponse)
async def reopen_books_period(
    period_id: uuid.UUID,
    body: BooksPeriodReopen,
    user_id: uuid.UUID = Depends(require_owner),
    service: BooksPeriodService = Depends(get_books_period_service),
) -> BooksPeriodResponse:
    return await service.reopen(period_id, user_id, body)
