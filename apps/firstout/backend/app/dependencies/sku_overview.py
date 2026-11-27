from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.sku_overview import SkuOverviewService
from app.services.sku_supplier_prices import SkuSupplierPriceService


def get_sku_overview_service(db: AsyncSession = Depends(get_db)) -> SkuOverviewService:
    return SkuOverviewService(db)


def get_sku_supplier_price_service(db: AsyncSession = Depends(get_db)) -> SkuSupplierPriceService:
    return SkuSupplierPriceService(db)
