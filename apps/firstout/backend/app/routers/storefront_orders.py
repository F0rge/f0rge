from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_deliveries_mutate, require_orders
from app.schemas.ops_commerce_order import (
    StorefrontCollectionStatusUpdate,
    StorefrontHandoffListResponse,
    StorefrontHandoffResponse,
)
from app.services.ops_commerce import OpsCommerceService

router = APIRouter(prefix="/api/v1/storefront/orders", tags=["storefront-orders"])


def get_storefront_order_service(
    db: AsyncSession = Depends(get_db),
) -> OpsCommerceService:
    return OpsCommerceService(db)


@router.get("", response_model=StorefrontHandoffListResponse)
async def list_storefront_handoffs(
    user_id: uuid.UUID = Depends(require_orders),
    service: OpsCommerceService = Depends(get_storefront_order_service),
) -> StorefrontHandoffListResponse:
    return await service.list_handoffs(user_id)


@router.post("/{handoff_id}/retry", response_model=StorefrontHandoffResponse)
async def retry_storefront_handoff(
    handoff_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_orders),
    service: OpsCommerceService = Depends(get_storefront_order_service),
) -> StorefrontHandoffResponse:
    return await service.retry_handoff(handoff_id, user_id)


@router.patch("/{handoff_id}/collection-status", response_model=StorefrontHandoffResponse)
async def update_storefront_collection_status(
    handoff_id: uuid.UUID,
    body: StorefrontCollectionStatusUpdate,
    user_id: uuid.UUID = Depends(require_deliveries_mutate),
    service: OpsCommerceService = Depends(get_storefront_order_service),
) -> StorefrontHandoffResponse:
    return await service.update_collection_status(handoff_id, body, user_id)
