"""Read APIs for imported detail: party addresses/contacts, supplier prices, history, bins."""

from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.schemas.page import Page, PageParams, get_page_params
from app.schemas.records import (
    AddressResponse,
    ContactResponse,
    PurchaseHistoryRow,
    SalesHistoryRow,
    StockByBinRow,
    SupplierPriceRow,
)
from app.services.records import RecordsService

records_router = APIRouter(prefix="/api/v1", tags=["records"])


def get_records_service(db: AsyncSession = Depends(get_db)) -> RecordsService:
    return RecordsService(db)


@records_router.get("/customers/{customer_id}/addresses", response_model=list[AddressResponse])
async def list_customer_addresses(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.customer_addresses(customer_id)


@records_router.get("/customers/{customer_id}/contacts", response_model=list[ContactResponse])
async def list_customer_contacts(
    customer_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.customer_contacts(customer_id)


@records_router.get("/suppliers/{supplier_id}/addresses", response_model=list[AddressResponse])
async def list_supplier_addresses(
    supplier_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.supplier_addresses(supplier_id)


@records_router.get("/suppliers/{supplier_id}/contacts", response_model=list[ContactResponse])
async def list_supplier_contacts(
    supplier_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.supplier_contacts(supplier_id)


@records_router.get("/supplier-prices", response_model=Page[SupplierPriceRow])
async def list_supplier_prices(
    supplier_id: Optional[uuid.UUID] = Query(None),
    sku_id: Optional[uuid.UUID] = Query(None),
    params: PageParams = Depends(get_page_params),
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.supplier_prices(user_id, params, supplier_id, sku_id)


@records_router.get("/history/sales", response_model=Page[SalesHistoryRow])
async def list_sales_history(
    customer_id: Optional[uuid.UUID] = Query(None),
    sku_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[datetime.date] = Query(None, alias="from"),
    date_to: Optional[datetime.date] = Query(None, alias="to"),
    params: PageParams = Depends(get_page_params),
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.sales_history(params, customer_id, sku_id, date_from, date_to)


@records_router.get("/history/purchases", response_model=Page[PurchaseHistoryRow])
async def list_purchase_history(
    supplier_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[datetime.date] = Query(None, alias="from"),
    date_to: Optional[datetime.date] = Query(None, alias="to"),
    params: PageParams = Depends(get_page_params),
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.purchase_history(user_id, params, supplier_id, date_from, date_to)


@records_router.get("/stock/by-bin", response_model=Page[StockByBinRow])
async def list_stock_by_bin(
    location_id: Optional[uuid.UUID] = Query(None),
    params: PageParams = Depends(get_page_params),
    _: uuid.UUID = Depends(get_current_user_id),
    service: RecordsService = Depends(get_records_service),
):
    return await service.stock_by_bin(params, location_id)
