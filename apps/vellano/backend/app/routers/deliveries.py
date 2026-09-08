from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_deliveries_service,
    require_deliveries_mutate,
)
from app.schemas.delivery import DeliveryComplete, DeliveryCreate, DeliveryResponse
from app.services.deliveries import DeliveriesService

deliveries_router = APIRouter(prefix="/api/v1/deliveries", tags=["deliveries"])


@deliveries_router.get("", response_model=list[DeliveryResponse])
async def list_deliveries(
    _: uuid.UUID = Depends(get_current_user_id),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.list()


@deliveries_router.post(
    "",
    response_model=DeliveryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_delivery(
    body: DeliveryCreate,
    user_id: uuid.UUID = Depends(require_deliveries_mutate),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.create(body, user_id)


@deliveries_router.get("/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery(
    delivery_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.get(delivery_id)


@deliveries_router.post("/{delivery_id}/pack", response_model=DeliveryResponse)
async def pack_delivery(
    delivery_id: uuid.UUID,
    _: uuid.UUID = Depends(require_deliveries_mutate),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.pack(delivery_id)


@deliveries_router.post("/{delivery_id}/complete", response_model=DeliveryResponse)
async def complete_delivery(
    delivery_id: uuid.UUID,
    body: DeliveryComplete = DeliveryComplete(),
    _: uuid.UUID = Depends(require_deliveries_mutate),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.complete(delivery_id, body)


@deliveries_router.post("/{delivery_id}/cancel", response_model=DeliveryResponse)
async def cancel_delivery(
    delivery_id: uuid.UUID,
    _: uuid.UUID = Depends(require_deliveries_mutate),
    service: DeliveriesService = Depends(get_deliveries_service),
):
    return await service.cancel(delivery_id)
