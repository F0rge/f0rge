"""Shared test helper: managed categories and materials exist before a SKU uses them.

SKU writes resolve a category name to an existing category and refuse unknown names, so
tests create the categories they use here instead of relying on implicit creation.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ops_commerce import SHOP_CATEGORIES
from app.models.catalogue_list import Material, SkuCategory


def _db(target) -> AsyncSession:
    # Accepts the session itself or a test client carrying ``test_db``.
    return getattr(target, "test_db", target)


async def ensure_category(
    target,
    name: str,
    *,
    parent_id: Optional[uuid.UUID] = None,
    shop_category: Optional[str] = None,
    archived: bool = False,
) -> SkuCategory:
    """The active category with this name (any case), created when missing.

    A new top-level category takes its shop section from ``SHOP_CATEGORIES`` unless one is
    given.
    """
    db = _db(target)
    if not archived:
        parent = (
            SkuCategory.parent_id.is_(None)
            if parent_id is None
            else SkuCategory.parent_id == parent_id
        )
        existing = await db.scalar(
            select(SkuCategory).where(
                parent,
                SkuCategory.is_archived.is_(False),
                func.lower(SkuCategory.name) == name.lower(),
            )
        )
        if existing is not None:
            return existing
    if shop_category is None and parent_id is None:
        shop_category = SHOP_CATEGORIES.get(name.strip().lower())
    row = SkuCategory(
        name=name,
        parent_id=parent_id,
        shop_category=shop_category,
        is_archived=archived,
    )
    db.add(row)
    await db.flush()
    return row


async def ensure_categories(target, *names: str) -> dict[str, SkuCategory]:
    return {name: await ensure_category(target, name) for name in names}


async def ensure_material(
    target, name: str, family: str = "other", *, archived: bool = False
) -> Material:
    db = _db(target)
    if not archived:
        existing = await db.scalar(
            select(Material).where(
                Material.is_archived.is_(False), func.lower(Material.name) == name.lower()
            )
        )
        if existing is not None:
            return existing
    row = Material(name=name, family=family, is_archived=archived)
    db.add(row)
    await db.flush()
    return row
