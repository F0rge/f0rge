from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.hypotheses import get_hypothesis_service, get_n_of_1_service
from app.middleware.auth import get_current_session
from app.schemas.hypothesis import (
    HypothesisCreate,
    HypothesisResponse,
    HypothesisUpdate,
    NOf1Response,
    NOf1Upsert,
)
from app.services.hypotheses import HypothesisService
from app.services.n_of_1 import NOf1Service

StatusFilter = Literal["live", "weakening", "killed", "parked"]

router = APIRouter(
    prefix="/api/v1/hypotheses",
    tags=["hypotheses"],
    dependencies=[Depends(get_current_session)],
)


@router.get("", response_model=list[HypothesisResponse])
async def list_hypotheses(
    status_filter: Optional[StatusFilter] = Query(None, alias="status"),
    service: HypothesisService = Depends(get_hypothesis_service),
):
    return await service.list(status_filter)


@router.post("", response_model=HypothesisResponse, status_code=status.HTTP_201_CREATED)
async def create_hypothesis(
    body: HypothesisCreate,
    service: HypothesisService = Depends(get_hypothesis_service),
):
    return await service.create(body)


@router.get("/n-of-1", response_model=Optional[NOf1Response])
async def get_n_of_1(service: NOf1Service = Depends(get_n_of_1_service)):
    return await service.get()


@router.put("/n-of-1", response_model=NOf1Response)
async def upsert_n_of_1(
    body: NOf1Upsert,
    service: NOf1Service = Depends(get_n_of_1_service),
):
    return await service.upsert(body)


@router.get("/{hypothesis_id}", response_model=HypothesisResponse)
async def get_hypothesis(
    hypothesis_id: uuid.UUID,
    service: HypothesisService = Depends(get_hypothesis_service),
):
    return await service.get(hypothesis_id)


@router.put("/{hypothesis_id}", response_model=HypothesisResponse)
async def update_hypothesis(
    hypothesis_id: uuid.UUID,
    body: HypothesisUpdate,
    service: HypothesisService = Depends(get_hypothesis_service),
):
    return await service.update(hypothesis_id, body)
