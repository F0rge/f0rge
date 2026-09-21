from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_sales_order_service,
    require_orders,
)
from app.models.sales_order import SalesOrderStatus
from app.schemas.page import Page, PageParams, get_page_params
from app.schemas.sales_order import (
    SalesOrderConfirm,
    SalesOrderListItem,
    SalesOrderPaymentCreate,
    SalesOrderResponse,
)
from app.services.sales_orders import SalesOrdersService

sales_orders_router = APIRouter(prefix="/api/v1/orders", tags=["sales-orders"])


@sales_orders_router.get("", response_model=Page[SalesOrderListItem])
async def list_sales_orders(
    params: PageParams = Depends(get_page_params),
    status: Optional[SalesOrderStatus] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.list(params, status=status)


@sales_orders_router.get("/{sales_order_id}", response_model=SalesOrderResponse)
async def get_sales_order(
    sales_order_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.get(sales_order_id)


@sales_orders_router.post("/{sales_order_id}/confirm", response_model=SalesOrderResponse)
async def confirm_sales_order(
    sales_order_id: uuid.UUID,
    body: SalesOrderConfirm,
    user_id: uuid.UUID = Depends(require_orders),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.confirm(sales_order_id, body, user_id)


@sales_orders_router.post(
    "/{sales_order_id}/payments",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_sales_order_payment(
    sales_order_id: uuid.UUID,
    body: SalesOrderPaymentCreate,
    user_id: uuid.UUID = Depends(require_orders),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.add_payment(sales_order_id, body, user_id)


@sales_orders_router.post("/{sales_order_id}/invoice", response_model=SalesOrderResponse)
async def remainder_invoice(
    sales_order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_orders),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.create_remainder_invoice(sales_order_id, user_id)


@sales_orders_router.post("/{sales_order_id}/cancel", response_model=SalesOrderResponse)
async def cancel_sales_order(
    sales_order_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_orders),
    service: SalesOrdersService = Depends(get_sales_order_service),
):
    return await service.cancel(sales_order_id, user_id)
