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
    return await orchestrator.extract(body)


@router.post("/enrich", response_model=EnrichResponse)
async def enrich_stage(
    body: EnrichRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> EnrichResponse:
    return await orchestrator.enrich(body)


@router.post("/gate", response_model=GateResponse)
async def gate_stage(
    body: GateRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> GateResponse:
    return orchestrator.gate(body)


@router.post("/persist", response_model=PersistResponse)
async def persist_stage(
    body: PersistRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> PersistResponse:
    return await orchestrator.persist(body)


@router.post("/fail", response_model=FailResponse)
async def fail_stage(
    body: FailRequest,
    orchestrator: MealAnalysisStageOrchestrator = Depends(get_meal_analysis_stage_orchestrator),
) -> FailResponse:
    return await orchestrator.fail(body)
