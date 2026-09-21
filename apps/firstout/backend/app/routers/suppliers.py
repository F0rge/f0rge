from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_supplier_service,
    require_catalogue_mutate,
)
from app.schemas.supplier import SupplierCreate, SupplierResponse
from app.services.suppliers import SupplierService

suppliers_router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


@suppliers_router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    _: uuid.UUID = Depends(get_current_user_id),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.list()


@suppliers_router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.create(body)
