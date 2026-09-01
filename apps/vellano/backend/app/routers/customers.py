from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_customers_crm_service,
    require_customers_mutate,
)
from app.schemas.customer_crm import (
    CustomerCrmCreate,
    CustomerCrmResponse,
    CustomerCrmUpdate,
)
from app.services.customers_crm import CustomersCrmService

customers_router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@customers_router.get("", response_model=list[CustomerCrmResponse])
async def list_customers(
    _: uuid.UUID = Depends(get_current_user_id),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.list()


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
    _: uuid.UUID = Depends(require_customers_mutate),
    service: CustomersCrmService = Depends(get_customers_crm_service),
):
    return await service.update(customer_id, body)
