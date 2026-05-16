from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.settings import get_settings_service
from app.middleware.auth import get_current_session
from app.models.session import AuthSession
from app.schemas.settings import (
    EmbeddingSettingsUpdate,
    ExternalTokenResponse,
    LLMSettingsUpdate,
    SettingsResponse,
    TestConnectionResponse,
)
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.factory import get_embedding_client, get_llm_client
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    service: SettingsService = Depends(get_settings_service),
    _session: AuthSession = Depends(get_current_session),
) -> SettingsResponse:
    return await service.get()


@router.put("/llm", response_model=SettingsResponse)
async def update_llm_settings(
    data: LLMSettingsUpdate,
    service: SettingsService = Depends(get_settings_service),
    _session: AuthSession = Depends(get_current_session),
) -> SettingsResponse:
    return await service.update_llm(data)


@router.put("/embedding", response_model=SettingsResponse)
async def update_embedding_settings(
    data: EmbeddingSettingsUpdate,
    service: SettingsService = Depends(get_settings_service),
    _session: AuthSession = Depends(get_current_session),
) -> SettingsResponse:
    return await service.update_embedding(data)


@router.post("/llm/test", response_model=TestConnectionResponse)
async def test_llm_connection(
    service: SettingsService = Depends(get_settings_service),
    llm: LLMClient = Depends(get_llm_client),
    _session: AuthSession = Depends(get_current_session),
) -> TestConnectionResponse:
    return await service.test_llm(llm)


@router.post("/embedding/test", response_model=TestConnectionResponse)
async def test_embedding_connection(
    service: SettingsService = Depends(get_settings_service),
    emb: EmbeddingClient = Depends(get_embedding_client),
    _session: AuthSession = Depends(get_current_session),
) -> TestConnectionResponse:
    return await service.test_embedding(emb)


@router.post("/external-token/regenerate", response_model=ExternalTokenResponse)
async def regenerate_external_token(
    service: SettingsService = Depends(get_settings_service),
    _session: AuthSession = Depends(get_current_session),
) -> ExternalTokenResponse:
    return await service.regenerate_external_token()


@router.post("/external-token/revoke", response_model=SettingsResponse)
async def revoke_external_token(
    service: SettingsService = Depends(get_settings_service),
    _session: AuthSession = Depends(get_current_session),
) -> SettingsResponse:
    return await service.revoke_external_token()
