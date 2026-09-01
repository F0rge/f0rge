from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_bill_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.bill import BillCreate, BillResponse
from app.services.bills import BillService

bills_router = APIRouter(prefix="/api/v1/bills", tags=["bills"])


@bills_router.get("", response_model=list[BillResponse])
async def list_bills(
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
):
    return await service.list()


@bills_router.post("", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    body: BillCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.create(body)


@bills_router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
):
    return await service.get(bill_id)


@bills_router.post("/{bill_id}/attachment", response_model=BillResponse)
async def upload_bill_attachment(
    bill_id: uuid.UUID,
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.upload_attachment(bill_id, file)


@bills_router.get("/{bill_id}/attachment", response_model=None)
async def get_bill_attachment(
    bill_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
) -> Response:
    return await service.serve_attachment(bill_id)
