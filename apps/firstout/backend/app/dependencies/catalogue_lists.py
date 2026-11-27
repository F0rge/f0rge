from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.catalogue_lists import CategoryService, MaterialService


def get_category_service(db: AsyncSession = Depends(get_db)) -> CategoryService:
    return CategoryService(db)


def get_material_service(db: AsyncSession = Depends(get_db)) -> MaterialService:
    return MaterialService(db)
