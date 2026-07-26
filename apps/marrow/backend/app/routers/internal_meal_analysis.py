from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.meal_analysis_internal import get_meal_analysis_stage_service
from app.schemas.meal_analysis_stages import (
    EnrichRequest,
    EnrichResponse,
    ExtractResponse,
    FailRequest,
    FailResponse,
    GateRequest,
    GateResponse,
    PersistRequest,
    PersistResponse,
    StagePhotoRef,
)
from app.services.meal_analysis_stages import MealAnalysisStageService

router = APIRouter(prefix="/api/v1/internal/meal-analysis", tags=["internal-meal-analysis"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_stage(
    body: StagePhotoRef,
    service: MealAnalysisStageService = Depends(get_meal_analysis_stage_service),
) -> ExtractResponse:
    return await service.extract(body.photo_id, body.user_id)


@router.post("/enrich", response_model=EnrichResponse)
async def enrich_stage(
    body: EnrichRequest,
    service: MealAnalysisStageService = Depends(get_meal_analysis_stage_service),
) -> EnrichResponse:
    return await service.enrich(body.user_id, body.vision)


@router.post("/gate", response_model=GateResponse)
async def gate_stage(
    body: GateRequest,
    service: MealAnalysisStageService = Depends(get_meal_analysis_stage_service),
) -> GateResponse:
    return service.gate(body.vision)


@router.post("/persist", response_model=PersistResponse)
async def persist_stage(
    body: PersistRequest,
    service: MealAnalysisStageService = Depends(get_meal_analysis_stage_service),
) -> PersistResponse:
    return await service.persist(
        user_id=body.user_id,
        analysis_id=body.analysis_id,
        photo_id=body.photo_id,
        raw_content=body.raw_content,
        vision=body.vision,
        ingredients=body.ingredients,
        status=body.status,
    )


@router.post("/fail", response_model=FailResponse)
async def fail_stage(
    body: FailRequest,
    service: MealAnalysisStageService = Depends(get_meal_analysis_stage_service),
) -> FailResponse:
    return await service.fail(
        user_id=body.user_id,
        analysis_id=body.analysis_id,
        error_message=body.error_message,
    )
