from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import (
    get_current_user_id,
    get_customers_crm_service,
    require_customers_mutate,
    require_customers_patch,
)
from app.schemas.customer_crm import (
    CustomerCrmCreate,
    CustomerCrmResponse,
    CustomerCrmUpdate,
)
from app.schemas.customer_portal import PortalMeResponse, PortalUserCreate
from app.services.customer_portal import CustomerPortalService
from app.services.customers_crm import CustomersCrmService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@customers_router.get("", response_model=list[CustomerCrmResponse])
async def list_customers(
    overdue: Optional[bool] = None,
    active_layby: Optional[bool] = None,
    on_hold: Optional[bool] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.list(overdue=overdue, active_layby=active_layby, on_hold=on_hold)


@customers_router.post(
    "",
    response_model=CustomerCrmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    body: CustomerCrmCreate,
    _: uuid.UUID = Depends(require_customers_mutate),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.create(body)


@customers_router.get("/{customer_id}", response_model=CustomerCrmResponse)
async def get_customer(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.get(customer_id)


@customers_router.patch("/{customer_id}", response_model=CustomerCrmResponse)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerCrmUpdate,
    user_id: uuid.UUID = Depends(require_customers_patch),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.update(customer_id, body, user_id)


@customers_router.post(
    "/{customer_id}/portal-users",
    response_model=PortalMeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_portal_user(
    customer_id: uuid.UUID,
    body: PortalUserCreate,
    _: uuid.UUID = Depends(require_customers_mutate),
    db: AsyncSession = Depends(get_db),
):
    return await CustomerPortalService(db).create_user(customer_id, body)
