from __future__ import annotations

import datetime
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.supplement_catalog import SupplementCatalogItem

_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


async def list_items(
    db: AsyncSession, include_archived: bool = False
) -> list[SupplementCatalogItem]:
    stmt = select(SupplementCatalogItem)
    if not include_archived:
        stmt = stmt.where(SupplementCatalogItem.archived.is_(False))
    stmt = stmt.order_by(
        SupplementCatalogItem.sort_order.asc(),
        SupplementCatalogItem.id.asc(),
    )
    return list((await db.execute(stmt)).scalars().all())


async def create_item(db: AsyncSession, key: str, label: str) -> SupplementCatalogItem:
    normalized = normalize_key(key)
    if not normalized or not _KEY_RE.match(normalized):
        raise ValidationError("Invalid key; must contain a-z, 0-9, or underscore.")

    existing = (
        await db.execute(
            select(SupplementCatalogItem).where(SupplementCatalogItem.key == normalized)
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
                select(SupplementCatalogItem).order_by(
                    SupplementCatalogItem.sort_order.desc()
                )
            )
        )
        .scalars()
        .first()
    )
    next_sort = (max_item.sort_order + 1) if max_item else 0

    item = SupplementCatalogItem(key=normalized, label=label, sort_order=next_sort)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, key: str, data: dict) -> SupplementCatalogItem:
    item = (
        await db.execute(
            select(SupplementCatalogItem).where(SupplementCatalogItem.key == key)
        )
    ).scalar_one_or_none()
    if not item:
        raise NotFoundError(f"Catalog item '{key}' not found.")

    for field, value in data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def touch(db: AsyncSession, keys: Iterable[str]) -> None:
    """Bulk-update first_used_at/last_used_at. Caller owns the transaction."""
    key_list = list(keys)
    if not key_list:
        return
    now = datetime.datetime.utcnow()
    existing = {
        item.key: item
        for item in (
            await db.execute(
                select(SupplementCatalogItem).where(
                    SupplementCatalogItem.key.in_(key_list)
                )
            )
        )
        .scalars()
        .all()
    }
    for key in key_list:
        item = existing.get(key)
        if item is None:
            continue
        if item.first_used_at is None:
            item.first_used_at = now
        item.last_used_at = now
