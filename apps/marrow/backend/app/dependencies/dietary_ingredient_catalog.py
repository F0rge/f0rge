from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.dietary_ingredient_catalog import DietaryIngredientCatalogService


def get_dietary_ingredient_catalog_service(
    db: AsyncSession = Depends(get_db),
) -> DietaryIngredientCatalogService:
    return DietaryIngredientCatalogService(db)
