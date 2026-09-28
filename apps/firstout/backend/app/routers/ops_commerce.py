from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ops_commerce import OpsProductsResponse
from app.schemas.ops_commerce_order import StorefrontHandoffResponse, StorefrontPaidOrder
from app.services.ops_commerce import OpsCommerceService

router = APIRouter(prefix="/api/v1/ops-commerce/v1", tags=["ops-commerce"])


def get_ops_commerce_service(db: AsyncSession = Depends(get_db)) -> OpsCommerceService:
    return OpsCommerceService(db)


@router.get("/products", response_model=OpsProductsResponse)
async def list_products(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    service: OpsCommerceService = Depends(get_ops_commerce_service),
) -> OpsProductsResponse:
    return await service.products(
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
    )


@router.post("/orders", response_model=StorefrontHandoffResponse)
async def accept_paid_order(
    body: StorefrontPaidOrder,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    service: OpsCommerceService = Depends(get_ops_commerce_service),
) -> JSONResponse:
    result, status_code = await service.accept_paid_order(
        body,
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
    )
    return JSONResponse(status_code=status_code, content=result.model_dump(mode="json"))
