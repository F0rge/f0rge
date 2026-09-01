from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user_id,
    get_inventory_service,
    get_purchase_order_service,
    require_catalogue_mutate,
    require_receive,
)
from app.schemas.inventory import InventorySkuResponse
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    ReceiveRequest,
)
from app.services.inventory import InventoryService
from app.services.purchase_orders import PurchaseOrderService

purchase_orders_router = APIRouter(prefix="/api/v1/purchase-orders", tags=["purchase-orders"])


@purchase_orders_router.get("", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    _: uuid.UUID = Depends(get_current_user_id),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.list()


@purchase_orders_router.post(
    "", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.create(data)


@purchase_orders_router.get("/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.get(po_id)


@purchase_orders_router.get("/{po_id}/packing-sheet", response_model=None)
async def get_packing_sheet(
    po_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
) -> Response:
    return await service.packing_sheet(po_id)


@purchase_orders_router.post("/{po_id}/on-water", response_model=PurchaseOrderResponse)
async def mark_on_water(
    po_id: uuid.UUID,
    _: uuid.UUID = Depends(require_catalogue_mutate),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.mark_on_water(po_id)


@purchase_orders_router.post("/{po_id}/land", response_model=PurchaseOrderResponse)
async def land_purchase_order(
    po_id: uuid.UUID,
    fx_to_zar: Decimal = Form(...),
    factory_invoice_number: str = Form(...),
    factory_amount: Decimal = Form(...),
    factory_currency: Optional[str] = Form(None),
    factory_file: UploadFile = File(...),
    freight_invoice_number: str = Form(...),
    freight_amount: Decimal = Form(...),
    freight_currency: str = Form(...),
    freight_file: UploadFile = File(...),
    clearance_invoice_number: str = Form(...),
    clearance_amount: Decimal = Form(...),
    clearance_currency: str = Form(...),
    clearance_file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_catalogue_mutate),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.land(
        po_id,
        user_id,
        fx_to_zar,
        factory_invoice_number,
        factory_amount,
        factory_currency,
        factory_file,
        freight_invoice_number,
        freight_amount,
        freight_currency,
        freight_file,
        clearance_invoice_number,
        clearance_amount,
        clearance_currency,
        clearance_file,
    )


receive_router = APIRouter(prefix="/api/v1", tags=["receive"])


@receive_router.post("/receive", response_model=PurchaseOrderResponse)
async def receive_purchase_order(
    data: ReceiveRequest,
    user_id: uuid.UUID = Depends(require_receive),
    service: PurchaseOrderService = Depends(get_purchase_order_service),
):
    return await service.receive(data, user_id)


inventory_router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@inventory_router.get("", response_model=list[InventorySkuResponse])
async def list_inventory(
    _: uuid.UUID = Depends(get_current_user_id),
    service: InventoryService = Depends(get_inventory_service),
):
    return await service.list()
