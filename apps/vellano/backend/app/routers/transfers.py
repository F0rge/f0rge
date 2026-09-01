from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_transfer_service, require_transfer
from app.schemas.transfer import TransferCreate, TransferResponse
from app.services.transfers import TransferService

transfers_router = APIRouter(prefix="/api/v1/transfers", tags=["transfers"])


@transfers_router.post("", response_model=TransferResponse, status_code=status.HTTP_200_OK)
async def create_transfer(
    data: TransferCreate,
    user_id: uuid.UUID = Depends(require_transfer),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.transfer(data, user_id)
