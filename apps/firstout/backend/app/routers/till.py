from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_till_orchestrator, require_till
from app.schemas.held_sale import (
    HeldSale,
    HeldSaleCreate,
    HeldSaleDelete,
    HeldSaleDeleteResult,
    HeldSaleNoteUpdate,
    HeldSaleResume,
    HeldSaleResumeResult,
    TillBasket,
    TillBasketUpdate,
)
from app.schemas.till_reservation import TillReservation
from app.schemas.sale_line_pricing import SalePricePreview
from app.schemas.till import TillPriceRequest, TillSaleCreate, TillSaleResponse
from app.services.held_sale import HeldSaleService
from app.services.till_basket import TillBasketService
from app.services.till_orchestrator import TillOrchestrator

till_router = APIRouter(prefix="/api/v1/till", tags=["till"])


@till_router.post("/price-preview", response_model=SalePricePreview)
async def preview_till_prices(
    body: TillPriceRequest,
    user_id: uuid.UUID = Depends(require_till),
    orchestrator: TillOrchestrator = Depends(get_till_orchestrator),
):
    return await orchestrator.preview_prices(body, user_id)


@till_router.post("/sales", response_model=TillSaleResponse, status_code=status.HTTP_201_CREATED)
async def create_till_sale(
    body: TillSaleCreate,
    user_id: uuid.UUID = Depends(require_till),
    orchestrator: TillOrchestrator = Depends(get_till_orchestrator),
):
    return await orchestrator.create_sale(body, user_id)


def get_held_sales(db: AsyncSession = Depends(get_db)) -> HeldSaleService:
    return HeldSaleService(db)


@till_router.get("/held-sales", response_model=list[HeldSale])
async def list_held_sales(
    location_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(require_till),
    service: HeldSaleService = Depends(get_held_sales),
) -> list[HeldSale]:
    return await service.list(location_id)


@till_router.post("/held-sales", response_model=HeldSale, status_code=status.HTTP_201_CREATED)
async def create_held_sale(
    body: HeldSaleCreate,
    user_id: uuid.UUID = Depends(require_till),
    service: HeldSaleService = Depends(get_held_sales),
) -> HeldSale:
    return await service.create(body, user_id)


@till_router.patch("/held-sales/{held_id}", response_model=HeldSale)
async def edit_held_sale_note(
    held_id: uuid.UUID,
    body: HeldSaleNoteUpdate,
    _user_id: uuid.UUID = Depends(require_till),
    service: HeldSaleService = Depends(get_held_sales),
) -> HeldSale:
    return await service.edit_note(held_id, body)


# exclude_unset keeps the response unchanged for callers that send no basket_id.
@till_router.post(
    "/held-sales/{held_id}/resume",
    response_model=HeldSaleResumeResult,
    response_model_exclude_unset=True,
)
async def resume_held_sale(
    held_id: uuid.UUID,
    body: HeldSaleResume,
    user_id: uuid.UUID = Depends(require_till),
    service: HeldSaleService = Depends(get_held_sales),
) -> HeldSaleResumeResult:
    return await service.resume(held_id, body, user_id)


@till_router.post("/held-sales/delete", response_model=HeldSaleDeleteResult)
async def delete_held_sales(
    body: HeldSaleDelete,
    _user_id: uuid.UUID = Depends(require_till),
    service: HeldSaleService = Depends(get_held_sales),
) -> HeldSaleDeleteResult:
    return await service.delete(body)


def get_baskets(db: AsyncSession = Depends(get_db)) -> TillBasketService:
    return TillBasketService(db)


@till_router.get("/basket", response_model=TillBasket)
async def get_till_basket(
    location_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_till),
    service: TillBasketService = Depends(get_baskets),
) -> TillBasket:
    return await service.get_or_create(location_id, user_id)


@till_router.put("/basket/{basket_id}", response_model=TillBasket)
async def replace_till_basket(
    basket_id: uuid.UUID,
    body: TillBasketUpdate,
    user_id: uuid.UUID = Depends(require_till),
    service: TillBasketService = Depends(get_baskets),
) -> TillBasket:
    return await service.replace(basket_id, body, user_id)


@till_router.get("/reservations", response_model=list[TillReservation])
async def list_till_reservations(
    location_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_till),
    service: TillBasketService = Depends(get_baskets),
) -> list[TillReservation]:
    """Stock held by other tills' open sales; the till combines it with its own inventory."""
    return await service.reservations(location_id, user_id)
