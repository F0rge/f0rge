from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import UserCRUD
from app.database import get_db
from app.middleware.auth import get_current_user_id
from app.models.user import UserRole
from app.services.auth import AuthService
from app.services.inventory import InventoryService
from app.services.locations import LocationService
from app.services.proformas import ProformaService
from app.services.purchase_orders import PurchaseOrderService
from app.services.skus import SkuService
from app.services.suppliers import SupplierService
from app.services.users import BootstrapService, ProfileService, UserService


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


def get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(db)


def get_bootstrap_service(db: AsyncSession = Depends(get_db)) -> BootstrapService:
    return BootstrapService(db)


def get_location_service(db: AsyncSession = Depends(get_db)) -> LocationService:
    return LocationService(db)


def get_supplier_service(db: AsyncSession = Depends(get_db)) -> SupplierService:
    return SupplierService(db)


def get_proforma_service(db: AsyncSession = Depends(get_db)) -> ProformaService:
    return ProformaService(db)


def get_sku_service(db: AsyncSession = Depends(get_db)) -> SkuService:
    return SkuService(db)


def get_purchase_order_service(db: AsyncSession = Depends(get_db)) -> PurchaseOrderService:
    return PurchaseOrderService(db)


def get_inventory_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    return InventoryService(db)


async def require_owner(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return user_id


async def require_location_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or warehouse access required",
        )
    return user_id


async def require_catalogue_mutate(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.BUYER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or buyer access required",
        )
    return user_id


async def require_receive(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    user = await UserCRUD(db).get_by_id(user_id)
    if user is None or user.role not in (UserRole.OWNER, UserRole.WAREHOUSE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or warehouse access required",
        )
    return user_id
