from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.treatments import get_treatment_service
from app.middleware.auth import get_current_session
from app.schemas.treatment import TreatmentCreate, TreatmentResponse, TreatmentUpdate
from app.services.treatments import TreatmentService

router = APIRouter(
    prefix="/api/v1/treatments",
    tags=["treatments"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[TreatmentResponse])
def list_treatments(
    active_on: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    service: TreatmentService = Depends(get_treatment_service),
):
    return service.list(active_on)


@router.get("/{treatment_id}", response_model=TreatmentResponse)
def get_treatment(
    treatment_id: int,
    service: TreatmentService = Depends(get_treatment_service),
):
    return service.get(treatment_id)


@router.post(
    "",
    response_model=TreatmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_treatment(
    body: TreatmentCreate,
    service: TreatmentService = Depends(get_treatment_service),
):
    return service.create(body)


@router.put("/{treatment_id}", response_model=TreatmentResponse)
def update_treatment(
    treatment_id: int,
    body: TreatmentUpdate,
    service: TreatmentService = Depends(get_treatment_service),
):
    return service.update(treatment_id, body)


@router.delete("/{treatment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_treatment(
    treatment_id: int,
    service: TreatmentService = Depends(get_treatment_service),
):
    service.delete(treatment_id)
