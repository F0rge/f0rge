from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.settings import get_settings_service
from app.middleware.auth import get_current_user_id
from app.schemas.settings import (
    CheckinDefaultsUpdate,
    EmbeddingSettingsUpdate,
    ExternalApiTokenListResponse,
    ExternalTokenCreate,
    ExternalTokenResponse,
    LLMSettingsUpdate,
    ProfileTagFilterUpdate,
    SettingsResponse,
    TaggedMealModeUpdate,
    TestConnectionResponse,
)
from app.services.llm.base import EmbeddingClient, LLMClient
from app.services.llm.factory import get_embedding_client, get_llm_client
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.get()


@router.put("/llm", response_model=SettingsResponse)
async def update_llm_settings(
    data: LLMSettingsUpdate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.update_llm(data)


@router.put("/embedding", response_model=SettingsResponse)
async def update_embedding_settings(
    data: EmbeddingSettingsUpdate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.update_embedding(data)


@router.post("/llm/test", response_model=TestConnectionResponse)
async def test_llm_connection(
    service: SettingsService = Depends(get_settings_service),
    llm: LLMClient = Depends(get_llm_client),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> TestConnectionResponse:
    return await service.test_llm(llm)


@router.post("/embedding/test", response_model=TestConnectionResponse)
async def test_embedding_connection(
    service: SettingsService = Depends(get_settings_service),
    emb: EmbeddingClient = Depends(get_embedding_client),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> TestConnectionResponse:
    return await service.test_embedding(emb)


@router.get("/external-tokens", response_model=ExternalApiTokenListResponse)
async def list_external_tokens(
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExternalApiTokenListResponse:
    return await service.list_external_tokens()


@router.post(
    "/external-tokens",
    response_model=ExternalTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_external_token(
    data: ExternalTokenCreate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> ExternalTokenResponse:
    return await service.create_external_token(data.name)


@router.delete("/external-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_external_token(
    token_id: uuid.UUID,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> None:
    await service.revoke_external_token(token_id)


@router.post("/onboarding/complete", response_model=SettingsResponse)
async def complete_onboarding(
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.complete_onboarding()


@router.put("/tagged-meal-mode", response_model=SettingsResponse)
async def update_tagged_meal_mode(
    body: TaggedMealModeUpdate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.update_tagged_meal_mode(body.tagged_meal_mode)


@router.put("/profile-tag-filter", response_model=SettingsResponse)
async def update_profile_tag_filter(
    body: ProfileTagFilterUpdate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.update_profile_tag_filter(body)


@router.put("/checkin-defaults", response_model=SettingsResponse)
async def update_checkin_defaults(
    body: CheckinDefaultsUpdate,
    service: SettingsService = Depends(get_settings_service),
    _user_id: uuid.UUID = Depends(get_current_user_id),
) -> SettingsResponse:
    return await service.update_checkin_defaults(body)
