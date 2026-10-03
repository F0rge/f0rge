from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_orders, require_storefront_handoff_read
from app.schemas.storefront_exceptions import (
    StorefrontExceptionAlertListResponse,
    StorefrontExceptionAlertRequest,
    StorefrontExceptionAlertResponse,
    StorefrontExceptionListResponse,
    StorefrontExceptionRepairRequest,
    StorefrontExceptionResponse,
)
from app.services.storefront_exceptions import StorefrontExceptionService

router = APIRouter(prefix="/api/v1/storefront/exceptions", tags=["storefront-exceptions"])


def get_storefront_exception_service(
    db: AsyncSession = Depends(get_db),
) -> StorefrontExceptionService:
    return StorefrontExceptionService(db)


@router.get("", response_model=StorefrontExceptionListResponse)
async def list_storefront_exceptions(
    user_id: uuid.UUID = Depends(require_storefront_handoff_read),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionListResponse:
    return await service.list_exceptions(user_id)


@router.post("/seed", response_model=StorefrontExceptionListResponse)
async def seed_storefront_exceptions(
    user_id: uuid.UUID = Depends(require_orders),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionListResponse:
    return await service.seed_fixtures(user_id)


@router.post("/alerts/test", response_model=StorefrontExceptionAlertResponse)
async def deliver_storefront_exception_alert(
    body: StorefrontExceptionAlertRequest,
    user_id: uuid.UUID = Depends(require_storefront_handoff_read),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionAlertResponse:
    return await service.deliver_test_alert(body, user_id)


@router.get("/alerts", response_model=StorefrontExceptionAlertListResponse)
async def list_storefront_exception_alerts(
    user_id: uuid.UUID = Depends(require_storefront_handoff_read),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionAlertListResponse:
    return await service.list_test_alerts(user_id)


@router.get("/{exception_id}", response_model=StorefrontExceptionResponse)
async def get_storefront_exception(
    exception_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_storefront_handoff_read),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionResponse:
    return await service.get_exception(exception_id, user_id)


@router.post("/{exception_id}/repair", response_model=StorefrontExceptionResponse)
async def repair_storefront_exception(
    exception_id: uuid.UUID,
    body: StorefrontExceptionRepairRequest,
    user_id: uuid.UUID = Depends(require_storefront_handoff_read),
    service: StorefrontExceptionService = Depends(get_storefront_exception_service),
) -> StorefrontExceptionResponse:
    return await service.repair(exception_id, body, user_id)
