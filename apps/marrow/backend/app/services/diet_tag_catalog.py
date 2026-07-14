from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.diet_tag_catalog import DietTagCatalogCRUD
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.diet_tag_catalog import DietTagCatalogItem
from f0rge_db.tenant import current_user_id

_KEY_RE = re.compile(r"^[a-z0-9-]+$")


def normalize_key(raw: str) -> str:
    # Diet tags use HYPHENATED keys (high-histamine, high-fodmap, ...) to match
    # the entry.diet_risk CSV format and diet_flags.FLAG_VOCAB. Do NOT mirror
    # supplement_catalog.normalize_key — that converts hyphens to underscores
    # and would break compat with seeded rows and historical entries.
    key = raw.strip().lower().replace(" ", "-").replace("_", "-")
    key = re.sub(r"[^a-z0-9-]", "", key)
    return key


class DietTagCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = DietTagCatalogCRUD(db)

    async def list_items(self, include_archived: bool = False) -> list[DietTagCatalogItem]:
        return await self.crud.list(include_archived=include_archived)

    async def create_item(self, key: str, label: str) -> DietTagCatalogItem:
        normalized = normalize_key(key)
        if not normalized or not _KEY_RE.match(normalized):
            raise ValidationError("Invalid key; must contain a-z, 0-9, or hyphen.")

        existing = await self.crud.get_by_key(normalized)
        if existing:
            if existing.archived:
                existing.archived = False
                existing.label = label
                return await self.crud.commit_refresh(existing)
            raise ConflictError(f"Catalog item '{normalized}' already exists.")

        max_item = await self.crud.get_max_sort_order_item()
        next_sort = (max_item.sort_order + 1) if max_item else 0

        item = DietTagCatalogItem(
            user_id=current_user_id(), key=normalized, label=label, sort_order=next_sort
        )
        self.crud.add(item)
        return await self.crud.commit_refresh(item)

    async def update_item(self, key: str, data: dict) -> DietTagCatalogItem:
        item = await self.crud.get_by_key(key)
        if not item:
            raise NotFoundError(f"Catalog item '{key}' not found.")

        for field, value in data.items():
            setattr(item, field, value)
        return await self.crud.commit_refresh(item)
