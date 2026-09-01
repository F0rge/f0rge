from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_cost_audit_service, require_cost_audit_view, require_owner
from app.schemas.cost_audit import UnitCostAuditResponse, UnitCostCorrectionRequest
from app.services.cost_audit import CostAuditService

cost_audit_router = APIRouter(prefix="/api/v1/skus", tags=["cost-audit"])


@cost_audit_router.get("/{sku_id}/cost-audit", response_model=list[UnitCostAuditResponse])
async def list_cost_audit(
    sku_id: uuid.UUID,
    location_id: Optional[uuid.UUID] = Query(default=None),
    _: uuid.UUID = Depends(require_cost_audit_view),
    service: CostAuditService = Depends(get_cost_audit_service),
) -> list[UnitCostAuditResponse]:
    return await service.list_for_sku(sku_id, location_id)


@cost_audit_router.patch(
    "/{sku_id}/unit-cost",
    response_model=UnitCostAuditResponse,
    status_code=status.HTTP_200_OK,
)
async def correct_unit_cost(
    sku_id: uuid.UUID,
    data: UnitCostCorrectionRequest,
    user_id: uuid.UUID = Depends(require_owner),
    service: CostAuditService = Depends(get_cost_audit_service),
) -> UnitCostAuditResponse:
    return await service.correct_unit_cost(sku_id, user_id, data)
