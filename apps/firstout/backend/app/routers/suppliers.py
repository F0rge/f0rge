from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_supplier_service,
    require_catalogue_mutate,
)
from app.schemas.supplier import SupplierCreate, SupplierResponse
from app.schemas.party_archive import PartyArchiveCounts, PartyArchiveUpdate
from app.services.suppliers import SupplierService

suppliers_router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])


@suppliers_router.get("", response_model=list[SupplierResponse])
async def list_suppliers(
    archived: bool = False,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.list(archived=archived)


@suppliers_router.get("/archive-counts", response_model=PartyArchiveCounts)
async def supplier_archive_counts(
    _: uuid.UUID = Depends(get_current_user_id),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.archive_counts()


@suppliers_router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.get(supplier_id)


@suppliers_router.patch("/{supplier_id}/archive", response_model=SupplierResponse)
async def archive_supplier(
    supplier_id: uuid.UUID,
    body: PartyArchiveUpdate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.set_archived(supplier_id, body.is_archived)


@suppliers_router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SupplierCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: SupplierService = Depends(get_supplier_service),
):
    return await service.create(body)
