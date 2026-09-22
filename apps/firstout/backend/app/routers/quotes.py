from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_quote_service,
    require_quotes,
)
from app.models.quote import QuoteStatus
from app.schemas.page import Page, PageParams, get_page_params
from app.schemas.quote import (
    QuoteAccept,
    QuoteCreate,
    QuoteListItem,
    QuoteResponse,
    QuoteUpdate,
)
from app.schemas.sales_order import SalesOrderResponse
from app.services.quotes import QuotesService

quotes_router = APIRouter(prefix="/api/v1/quotes", tags=["quotes"])


@quotes_router.get("", response_model=Page[QuoteListItem])
async def list_quotes(
    params: PageParams = Depends(get_page_params),
    status: Optional[QuoteStatus] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.list(params, status=status)


@quotes_router.post("", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    body: QuoteCreate,
    user_id: uuid.UUID = Depends(require_quotes),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.create(body, user_id)


@quotes_router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.get(quote_id)


@quotes_router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: uuid.UUID,
    body: QuoteUpdate,
    _: uuid.UUID = Depends(require_quotes),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.update(quote_id, body)


@quotes_router.post("/{quote_id}/mark-sent", response_model=QuoteResponse)
async def mark_quote_sent(
    quote_id: uuid.UUID,
    _: uuid.UUID = Depends(require_quotes),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.mark_sent(quote_id)


@quotes_router.post("/{quote_id}/cancel", response_model=QuoteResponse)
async def cancel_quote(
    quote_id: uuid.UUID,
    _: uuid.UUID = Depends(require_quotes),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.cancel(quote_id)


@quotes_router.post("/{quote_id}/accept", response_model=SalesOrderResponse)
async def accept_quote(
    quote_id: uuid.UUID,
    body: QuoteAccept,
    user_id: uuid.UUID = Depends(require_quotes),
    service: QuotesService = Depends(get_quote_service),
):
    return await service.accept(quote_id, body, user_id)


@quotes_router.get("/{quote_id}/pdf", response_model=None)
async def get_quote_pdf(
    quote_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: QuotesService = Depends(get_quote_service),
) -> Response:
    return await service.serve_pdf(quote_id)
