from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_bill_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.bill import BillCreate, BillListItem, BillResponse, BillSummary, BillUpdate
from app.schemas.page import Page, PageParams, get_page_params
from app.services.bills import BillService

bills_router = APIRouter(prefix="/api/v1/bills", tags=["bills"])


@bills_router.get("", response_model=Page[BillListItem])
async def list_bills(
    params: PageParams = Depends(get_page_params),
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
):
    return await service.list(params)


@bills_router.post("", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    body: BillCreate,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.create(body, user_id)


@bills_router.get("/summary", response_model=BillSummary)
async def bill_summary(
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
):
    return await service.summary()


@bills_router.get("/{bill_id}", response_model=BillResponse)
async def get_bill(
    bill_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
):
    return await service.get(bill_id)


@bills_router.patch("/{bill_id}", response_model=BillResponse)
async def update_bill(
    bill_id: uuid.UUID,
    body: BillUpdate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.update(bill_id, body)


@bills_router.post("/{bill_id}/submit", response_model=BillResponse)
async def submit_bill(
    bill_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.submit(bill_id)


@bills_router.post("/{bill_id}/approve", response_model=BillResponse)
async def approve_bill(
    bill_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.approve(bill_id, user_id)


@bills_router.post("/{bill_id}/archive", response_model=BillResponse)
async def archive_bill(
    bill_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.set_archived(bill_id, True, user_id)


@bills_router.post("/{bill_id}/restore", response_model=BillResponse)
async def restore_bill(
    bill_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.set_archived(bill_id, False)


@bills_router.post("/{bill_id}/attachments", response_model=BillResponse)
async def upload_bill_attachment(
    bill_id: uuid.UUID,
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.add_attachment(bill_id, file, user_id)


@bills_router.get("/{bill_id}/attachments/{attachment_id}", response_model=None)
async def get_bill_attachment(
    bill_id: uuid.UUID,
    attachment_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BillService = Depends(get_bill_service),
) -> Response:
    return await service.serve_attachment(bill_id, attachment_id)


@bills_router.delete("/{bill_id}/attachments/{attachment_id}", response_model=BillResponse)
async def delete_bill_attachment(
    bill_id: uuid.UUID,
    attachment_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BillService = Depends(get_bill_service),
):
    return await service.remove_attachment(bill_id, attachment_id)
