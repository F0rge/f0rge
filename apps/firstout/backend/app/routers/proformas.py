from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_proforma_service,
    require_catalogue_mutate,
)
from app.schemas.proforma import ProformaResponse
from app.services.proformas import ProformaService

proformas_router = APIRouter(prefix="/api/v1/proformas", tags=["proformas"])


@proformas_router.get("", response_model=list[ProformaResponse])
async def list_proformas(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ProformaService = Depends(get_proforma_service),
):
    return await service.list()


@proformas_router.post("", response_model=ProformaResponse, status_code=status.HTTP_201_CREATED)
async def create_proforma(
    supplier_id: uuid.UUID = Form(...),
    invoice_number: str = Form(...),
    invoice_date: datetime.date = Form(...),
    currency: Optional[str] = Form(None),
    file: UploadFile = File(...),
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: ProformaService = Depends(get_proforma_service),
):
    return await service.create(supplier_id, invoice_number, invoice_date, currency, file)


@proformas_router.get("/{proforma_id}", response_model=ProformaResponse)
async def get_proforma(
    proforma_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: ProformaService = Depends(get_proforma_service),
):
    return await service.get(proforma_id)


@proformas_router.get("/{proforma_id}/file", response_model=None)
async def get_proforma_file(
    proforma_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: ProformaService = Depends(get_proforma_service),
) -> Response:
    return await service.serve_file(proforma_id)
