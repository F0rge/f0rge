from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_sales_staff_service,
    require_owner,
    require_sales_staff_options,
)
from app.schemas.sales_staff import (
    SalesStaffCreate,
    SalesStaffOption,
    SalesStaffResponse,
    SalesStaffUpdate,
)
from app.services.sales_staff import SalesStaffService

sales_staff_router = APIRouter(prefix="/api/v1/sales-staff", tags=["sales-staff"])

_ACTIVE = {"active": True, "inactive": False, "all": None}


@sales_staff_router.get("", response_model=list[SalesStaffResponse])
async def list_sales_staff(
    status: Literal["active", "inactive", "all"] = "all",
    _: uuid.UUID = Depends(require_owner),
    service: SalesStaffService = Depends(get_sales_staff_service),
):
    return await service.list(active=_ACTIVE[status])


@sales_staff_router.get("/options", response_model=list[SalesStaffOption])
async def list_sales_staff_options(
    _: uuid.UUID = Depends(require_sales_staff_options),
    service: SalesStaffService = Depends(get_sales_staff_service),
):
    return await service.list(active=True)


@sales_staff_router.post("", response_model=SalesStaffResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_staff(
    body: SalesStaffCreate,
    _: uuid.UUID = Depends(require_owner),
    service: SalesStaffService = Depends(get_sales_staff_service),
):
    return await service.create(body)


@sales_staff_router.patch("/{staff_id}", response_model=SalesStaffResponse)
async def update_sales_staff(
    staff_id: uuid.UUID,
    body: SalesStaffUpdate,
    _: uuid.UUID = Depends(require_owner),
    service: SalesStaffService = Depends(get_sales_staff_service),
):
    return await service.update(staff_id, body)


@sales_staff_router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sales_staff(
    staff_id: uuid.UUID,
    _: uuid.UUID = Depends(require_owner),
    service: SalesStaffService = Depends(get_sales_staff_service),
):
    await service.delete(staff_id)
