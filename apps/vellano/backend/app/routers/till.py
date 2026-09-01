from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import get_till_orchestrator, require_till
from app.schemas.till import TillSaleCreate, TillSaleResponse
from app.services.till_orchestrator import TillOrchestrator

till_router = APIRouter(prefix="/api/v1/till", tags=["till"])


@till_router.post("/sales", response_model=TillSaleResponse, status_code=status.HTTP_201_CREATED)
async def create_till_sale(
    body: TillSaleCreate,
    _: uuid.UUID = Depends(require_till),
    orchestrator: TillOrchestrator = Depends(get_till_orchestrator),
):
    return await orchestrator.create_sale(body)
