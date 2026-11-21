from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_settings_service,
    require_settings,
)
from app.schemas.document_template import (
    DocumentTemplate,
    DocumentTemplatePreview,
    DocumentTemplateResponse,
)
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.settings import SettingsService

settings_router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@settings_router.get("", response_model=SettingsResponse)
async def get_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.get_for_user(user_id)


@settings_router.patch("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.update(user_id, data)


@settings_router.post("/logo", response_model=SettingsResponse)
async def upload_logo(
    logo: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> SettingsResponse:
    return await service.upload_logo(user_id, logo)


@settings_router.get("/logo")
async def get_logo(
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
):
    return await service.serve_logo(user_id)


@settings_router.get("/document-template", response_model=DocumentTemplateResponse)
async def get_document_template(
    _: uuid.UUID = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
) -> DocumentTemplateResponse:
    return await service.get_document_template()


@settings_router.put("/document-template", response_model=DocumentTemplateResponse)
async def update_document_template(
    template: DocumentTemplate,
    _: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> DocumentTemplateResponse:
    return await service.update_document_template(template)


@settings_router.post(
    "/document-template/preview",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def preview_document_template(
    body: DocumentTemplatePreview,
    _: uuid.UUID = Depends(require_settings),
    service: SettingsService = Depends(get_settings_service),
) -> Response:
    return await service.preview_document_template(body)
