"""Category, sub-category and material lookups shared by every path that writes a SKU.

The lists are controlled: only the categories and materials APIs (and the migration) create
rows. ``seed_categories`` is the one exception, for playground seeds and local fixtures.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalogue_list import Material, SkuCategory
from app.models.sku import Sku
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx

logger = logging.getLogger(__name__)

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
    """The active category (top-level when ``parent_id`` is None) with this name.

    Case- and accent-insensitive, the way the categories service compares names ("Decor"
    finds "Décor"); that service keeps folded names unique per level.
    """
    from app.services.catalogue_lists import fold_name

    parent = (
        SkuCategory.parent_id.is_(None) if parent_id is None else SkuCategory.parent_id == parent_id
    )
    active = select(SkuCategory).where(
        SkuCategory.team_id == tenant_id_ctx.get(), SkuCategory.is_archived.is_(False), parent
    )
    exact = await db.scalar(active.where(func.lower(SkuCategory.name) == name.strip().lower()))
    if exact is not None:
        return exact
    key = fold_name(name)
    # ponytail: scans one level's active names; fine for a managed list of tens of rows.
    return next((row for row in await db.scalars(active) if fold_name(row.name) == key), None)


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


async def relink_sku_categories(db: AsyncSession) -> tuple[int, int]:
    """Startup repair: make each SKU's ``category_id`` agree with its ``category`` text.

    The previous backend (during a release, or for as long as an automatic rollback runs it
    on the new schema) writes only the text. Per team, under the session's tenant context:

    - text naming a top-level category (``lower(btrim(text)) = lower(name)``, the folding the
      unique index uses; an active row wins over an archived one) but a missing or different
      link: linked to it, text set to its spelling, a sub-category that no longer fits cleared;
    - blank text with a link: link and sub-category cleared;
    - text naming no category (accents folded too): counted and logged, never created; a
      link it still carries is cleared with its sub-category, so the SKU leaves its old
      shop section and posts by its text like any unmapped category.

    One query when nothing needs fixing. Idempotent; replicas racing write the same values.
    Returns ``(fixed, unmatched)``.
    """
    team_id = tenant_id_ctx.get()
    match = (
        select(SkuCategory.id)
        .where(
            SkuCategory.team_id == Sku.team_id,
            SkuCategory.parent_id.is_(None),
            func.lower(SkuCategory.name) == func.lower(func.btrim(Sku.category)),
        )
        .order_by(SkuCategory.is_archived, SkuCategory.created_at, SkuCategory.id)
        .limit(1)
        .correlate(Sku)
        .scalar_subquery()
    )
    blank = func.btrim(func.coalesce(Sku.category, "")) == ""
    rows = (
        await db.execute(
            select(Sku, match.label("match"))
            .where(
                Sku.team_id == team_id,
                or_(
                    and_(blank, Sku.category_id.is_not(None)),
                    and_(~blank, or_(match.is_(None), Sku.category_id.is_distinct_from(match))),
                ),
            )
            .order_by(Sku.id)
        )
    ).all()
    if not rows:
        return 0, 0
    from app.services.catalogue_lists import fold_name

    # SQL matched case- and space-insensitively; fall back to the accent folding the
    # categories service uses ("Decor" is "Décor"), active categories first.
    top_level: list[SkuCategory] = []
    if any(found is None and (sku.category or "").strip() for sku, found in rows):
        top_level = list(
            await db.scalars(
                select(SkuCategory)
                .where(SkuCategory.team_id == team_id, SkuCategory.parent_id.is_(None))
                .order_by(SkuCategory.is_archived, SkuCategory.created_at, SkuCategory.id)
            )
        )
    fixes: list[tuple[Sku, Optional[uuid.UUID]]] = []
    unmatched: list[Sku] = []
    for sku, found in rows:
        text = (sku.category or "").strip()
        if text and found is None:
            key = fold_name(text)
            found = next((row.id for row in top_level if fold_name(row.name) == key), None)
            if found is None:
                # Unmanaged name: never create it. A stale link would keep the SKU in its
                # old shop section and posting, so it is cleared; the text stays.
                unmatched.append(sku)
                if sku.category_id is not None:
                    fixes.append((sku, None))
                continue
            if found == sku.category_id:
                continue  # text and link already agree once accents are folded
        fixes.append((sku, found))
    categories = await categories_by_id(
        db, [found for _, found in fixes] + [sku.subcategory_id for sku, _ in fixes]
    )
    async with unit_of_work(db):
        for sku, found in fixes:
            sub = categories.get(sku.subcategory_id) if sku.subcategory_id else None
            # Both columns in one UPDATE: the database checks the pair.
            sku.category_id = found
            sku.subcategory_id = sub.id if sub is not None and sub.parent_id == found else None
            if found is not None:
                sku.category = categories[found].name
    if fixes:
        logger.warning(
            "Re-linked or unlinked the category of %d SKU(s) written by an older backend",
            len(fixes),
        )
    if unmatched:
        logger.warning(
            "%d SKU(s) name a category that is not in the managed list; add it in Settings: %s",
            len(unmatched),
            ", ".join(sorted({sku.category.strip() for sku in unmatched})[:20]),
        )
    return len(fixes), len(unmatched)
