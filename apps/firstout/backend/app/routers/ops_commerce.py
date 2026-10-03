from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_storefront_refund_workflow_service
from app.schemas.ops_commerce import OpsProductsResponse
from app.schemas.ops_commerce_order import (
    StorefrontFulfillmentEventAck,
    StorefrontFulfillmentEventAckResponse,
    StorefrontFulfillmentEventList,
    StorefrontHandoffResponse,
    StorefrontPaidOrder,
    StorefrontRefundCommandList,
    StorefrontRefundDispatchOutcome,
    StorefrontRefundProviderEvent,
    StorefrontRefundProviderEventResponse,
    StorefrontRefundResponse,
)
from app.services.ops_commerce import OpsCommerceService
from app.services.storefront_refund_workflow import StorefrontRefundWorkflowService

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


@router.get("/fulfillment-events", response_model=StorefrontFulfillmentEventList)
async def list_fulfillment_events(
    request: Request,
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    service: OpsCommerceService = Depends(get_ops_commerce_service),
) -> StorefrontFulfillmentEventList:
    return await service.list_fulfillment_events(
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
        limit=max(1, min(limit, 500)),
    )


@router.post(
    "/fulfillment-events/ack",
    response_model=StorefrontFulfillmentEventAckResponse,
)
async def acknowledge_fulfillment_events(
    body: StorefrontFulfillmentEventAck,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    service: OpsCommerceService = Depends(get_ops_commerce_service),
) -> StorefrontFulfillmentEventAckResponse:
    return await service.acknowledge_fulfillment_events(
        body.event_ids,
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
    )


@router.get("/refund-commands", response_model=StorefrontRefundCommandList)
async def list_refund_commands(
    request: Request,
    limit: int = 100,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    refunds: StorefrontRefundWorkflowService = Depends(get_storefront_refund_workflow_service),
) -> StorefrontRefundCommandList:
    return await refunds.list_machine_refund_commands(
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
        limit=max(1, min(limit, 500)),
    )


@router.post(
    "/refund-commands/{request_id}/outcome",
    response_model=StorefrontRefundResponse,
)
async def record_refund_dispatch_outcome(
    request_id: uuid.UUID,
    body: StorefrontRefundDispatchOutcome,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    refunds: StorefrontRefundWorkflowService = Depends(get_storefront_refund_workflow_service),
) -> StorefrontRefundResponse:
    return await refunds.record_machine_dispatch_outcome(
        request_id,
        body,
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
    )


@router.post(
    "/refund-events",
    response_model=StorefrontRefundProviderEventResponse,
)
async def record_refund_event(
    body: StorefrontRefundProviderEvent,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_ops_company_id: Optional[str] = Header(default=None),
    refunds: StorefrontRefundWorkflowService = Depends(get_storefront_refund_workflow_service),
) -> StorefrontRefundProviderEventResponse:
    return await refunds.record_machine_provider_event(
        body,
        authorization=authorization,
        requested_company=x_ops_company_id,
        request_host=request.url.hostname or "",
    )
