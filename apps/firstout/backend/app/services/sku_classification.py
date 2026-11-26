"""Category, sub-category and material lookups shared by every path that writes a SKU.

The lists are controlled: only the categories and materials APIs (and the migration) create
rows. ``seed_categories`` is the one exception, for playground seeds and local fixtures.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue_list import Material, SkuCategory
from f0rge_db.organisation import tenant_id_ctx

# skus.fabric is now a derived label; "-" is the placeholder documents hide.
FABRIC_PLACEHOLDER = "-"
DUPLICATE_FINISH_MESSAGE = "Another SKU already has this design, colour and material."


def unknown_category_message(name: str) -> str:
    return f"Unknown category '{name}'. Add it in Settings first."


def unknown_subcategory_message(name: str) -> str:
    return f"Unknown sub-category '{name}'. Add it in Settings first."


def finish_label(colour_name: Optional[str], material_name: Optional[str]) -> Optional[str]:
    """``"{colour} {material}"`` trimmed, or None when both are empty."""
    parts = [part.strip() for part in (colour_name, material_name) if part and part.strip()]
    return " ".join(parts) or None


async def category_by_name(
    db: AsyncSession, name: str, *, parent_id: Optional[uuid.UUID] = None
) -> Optional[SkuCategory]:
    """The active category (top-level when ``parent_id`` is None) with this name, any case."""
    parent = (
        SkuCategory.parent_id.is_(None) if parent_id is None else SkuCategory.parent_id == parent_id
    )
    return await db.scalar(
        select(SkuCategory).where(
            SkuCategory.team_id == tenant_id_ctx.get(),
            SkuCategory.is_archived.is_(False),
            parent,
            func.lower(SkuCategory.name) == name.strip().lower(),
        )
    )


async def categories_by_id(
    db: AsyncSession, ids: Iterable[Optional[uuid.UUID]]
) -> dict[uuid.UUID, SkuCategory]:
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await db.scalars(
        select(SkuCategory).where(
            SkuCategory.team_id == tenant_id_ctx.get(), SkuCategory.id.in_(wanted)
        )
    )
    return {row.id: row for row in rows}


async def materials_by_id(
    db: AsyncSession, ids: Iterable[Optional[uuid.UUID]]
) -> dict[uuid.UUID, Material]:
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await db.scalars(
        select(Material).where(Material.team_id == tenant_id_ctx.get(), Material.id.in_(wanted))
    )
    return {row.id: row for row in rows}


async def seed_categories(db: AsyncSession, names: Iterable[str]) -> dict[str, SkuCategory]:
    """Seeds and local fixtures only: make sure these top-level categories exist.

    Keyed by lower-case name. New rows take their shop section from ``SHOP_CATEGORIES``.
    """
    from app.crud.ops_commerce import SHOP_CATEGORIES

    found: dict[str, SkuCategory] = {}
    for name in dict.fromkeys(name.strip() for name in names if name and name.strip()):
        key = name.lower()
        row = await category_by_name(db, name)
        if row is None:
            row = SkuCategory(name=name, shop_category=SHOP_CATEGORIES.get(key))
            db.add(row)
            await db.flush()
        found[key] = row
    return found
