from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_transfer_service,
    require_transfer,
    require_transfer_receive,
)
from app.models.transfer import TransferStatus
from app.schemas.transfer import TransferCreate, TransferReceive, TransferResponse
from app.services.transfers import TransferService

transfers_router = APIRouter(prefix="/api/v1/transfers", tags=["transfers"])


@transfers_router.get("", response_model=list[TransferResponse])
async def list_transfers(
    status: Optional[TransferStatus] = None,
    to_location_id: Optional[uuid.UUID] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.list(status=status, to_location_id=to_location_id)


@transfers_router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    data: TransferCreate,
    user_id: uuid.UUID = Depends(require_transfer),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.create(data, user_id)


@transfers_router.get("/{transfer_id}", response_model=TransferResponse)
async def get_transfer(
    transfer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.get(transfer_id)


@transfers_router.post("/{transfer_id}/dispatch", response_model=TransferResponse)
async def dispatch_transfer(
    transfer_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_transfer),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.dispatch(transfer_id, user_id)


@transfers_router.get("/{transfer_id}/pdf", response_model=None)
async def get_transfer_pdf(
    transfer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: TransferService = Depends(get_transfer_service),
) -> Response:
    return await service.serve_pdf(transfer_id)


@transfers_router.post("/{transfer_id}/receive", response_model=TransferResponse)
async def receive_transfer(
    transfer_id: uuid.UUID,
    data: TransferReceive,
    user_id: uuid.UUID = Depends(require_transfer_receive),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.receive(transfer_id, data, user_id)


@transfers_router.post("/{transfer_id}/cancel", response_model=TransferResponse)
async def cancel_transfer(
    transfer_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_transfer),
    service: TransferService = Depends(get_transfer_service),
):
    return await service.cancel(transfer_id, user_id)
