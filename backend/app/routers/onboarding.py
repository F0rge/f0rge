from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.onboarding_setup import get_onboarding_setup_service
from app.middleware.auth import get_current_session
from app.schemas.onboarding import (
    CatalogSetupRequest,
    CatalogSetupResponse,
    CatalogSuggestionsResponse,
)
from app.services.onboarding_setup import OnboardingSetupService

router = APIRouter(
    prefix="/api/v1",
    tags=["onboarding"],
    dependencies=[Depends(get_current_session)],
)


@router.get("/catalog/suggestions", response_model=CatalogSuggestionsResponse)
async def list_catalog_suggestions(
    service: OnboardingSetupService = Depends(get_onboarding_setup_service),
):
    return service.get_suggestions()


@router.post(
    "/onboarding/catalog-setup",
    response_model=CatalogSetupResponse,
    status_code=status.HTTP_200_OK,
)
async def apply_catalog_setup(
    body: CatalogSetupRequest,
    service: OnboardingSetupService = Depends(get_onboarding_setup_service),
):
    return await service.apply_catalog_setup(body)
