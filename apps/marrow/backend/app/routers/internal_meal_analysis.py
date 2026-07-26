from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.meal_analysis_stage import get_meal_analysis_stage_orchestrator
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
from app.services.meal_analysis_stage_orchestrator import MealAnalysisStageOrchestrator

router = APIRouter(prefix="/api/v1/internal/meal-analysis", tags=["internal-meal-analysis"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_stage(
    body: StagePhotoRef,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> ExtractResponse:
    return await orchestrator.extract(body.photo_id, body.user_id)


@router.post("/enrich", response_model=EnrichResponse)
async def enrich_stage(
    body: EnrichRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> EnrichResponse:
    return await orchestrator.enrich(body.user_id, body.vision)


@router.post("/gate", response_model=GateResponse)
async def gate_stage(
    body: GateRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> GateResponse:
    return orchestrator.gate(body.vision)


@router.post("/persist", response_model=PersistResponse)
async def persist_stage(
    body: PersistRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> PersistResponse:
    return await orchestrator.persist(
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
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> FailResponse:
    return await orchestrator.fail(
        user_id=body.user_id,
        analysis_id=body.analysis_id,
        error_message=body.error_message,
    )
