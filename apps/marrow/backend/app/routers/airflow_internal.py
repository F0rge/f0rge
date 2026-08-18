from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.airflow_meal import (
    get_airflow_meal_analysis_service,
    require_airflow_service_auth,
)
from app.schemas.airflow_meal import (
    MealAnalysisCompleteRequest,
    MealAnalysisFailRequest,
    MealAnalysisResolveRequest,
    MealAnalysisResolveResponse,
)
from app.services.airflow_meal_analysis import AirflowMealAnalysisService

router = APIRouter(
    prefix="/api/v1/internal/airflow",
    tags=["internal-airflow"],
    dependencies=[Depends(require_airflow_service_auth)],
)


@router.post(
    "/meal-analysis/resolve",
    response_model=MealAnalysisResolveResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_meal_analysis(
    body: MealAnalysisResolveRequest,
    service: AirflowMealAnalysisService = Depends(get_airflow_meal_analysis_service),
):
    return await service.resolve(body.photo_id, body.user_id)


@router.post(
    "/meal-analysis/{analysis_id}/complete",
    status_code=status.HTTP_200_OK,
)
async def complete_meal_analysis(
    analysis_id: int,
    body: MealAnalysisCompleteRequest,
    service: AirflowMealAnalysisService = Depends(get_airflow_meal_analysis_service),
):
    return await service.complete(analysis_id, body)


@router.post(
    "/meal-analysis/{analysis_id}/fail",
    status_code=status.HTTP_200_OK,
)
async def fail_meal_analysis(
    analysis_id: int,
    body: MealAnalysisFailRequest,
    service: AirflowMealAnalysisService = Depends(get_airflow_meal_analysis_service),
):
    return await service.fail(analysis_id, body.error_message, body.user_id)
