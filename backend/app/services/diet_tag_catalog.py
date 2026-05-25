from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.diet_tag_catalog import DietTagCatalogItem

_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


async def list_items(
    db: AsyncSession, include_archived: bool = False
) -> list[DietTagCatalogItem]:
    stmt = select(DietTagCatalogItem)
    if not include_archived:
        stmt = stmt.where(DietTagCatalogItem.archived.is_(False))
    stmt = stmt.order_by(
        DietTagCatalogItem.sort_order.asc(),
        DietTagCatalogItem.id.asc(),
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_item(db: AsyncSession, key: str, label: str) -> DietTagCatalogItem:
    normalized = normalize_key(key)
    if not normalized or not _KEY_RE.match(normalized):
        raise ValidationError("Invalid key; must contain a-z, 0-9, or underscore.")

    existing = (
        await db.execute(
            select(DietTagCatalogItem).where(DietTagCatalogItem.key == normalized)
        )
    ).scalar_one_or_none()

    if existing:
        if existing.archived:
            existing.archived = False
            existing.label = label
            await db.commit()
            await db.refresh(existing)
            return existing
        raise ConflictError(f"Catalog item '{normalized}' already exists.")

    max_item = (
        (
            await db.execute(
                select(DietTagCatalogItem).order_by(
                    DietTagCatalogItem.sort_order.desc()
                )
            )
        )
        .scalars()
        .first()
    )
    next_sort = (max_item.sort_order + 1) if max_item else 0

    item = DietTagCatalogItem(key=normalized, label=label, sort_order=next_sort)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, key: str, data: dict) -> DietTagCatalogItem:
    item = (
        await db.execute(
            select(DietTagCatalogItem).where(DietTagCatalogItem.key == key)
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError(f"Catalog item '{key}' not found.")

    for field, value in data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item
