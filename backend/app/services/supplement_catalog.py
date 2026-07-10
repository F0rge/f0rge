from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.supplement_catalog import SupplementCatalogCRUD
from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.supplement_catalog import SupplementCatalogItem
from app.tenant import current_user_id

_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


class SupplementCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SupplementCatalogCRUD(db)

    async def list_items(self, include_archived: bool = False) -> list[SupplementCatalogItem]:
        return await self.crud.list(include_archived=include_archived)

    async def create_item(self, key: str, label: str) -> SupplementCatalogItem:
        normalized = normalize_key(key)
        if not normalized or not _KEY_RE.match(normalized):
            raise ValidationError("Invalid key; must contain a-z, 0-9, or underscore.")

        existing = await self.crud.get_by_key(normalized)
        if existing:
            if existing.archived:
                existing.archived = False
                existing.label = label
                return await self.crud.commit_refresh(existing)
            raise ConflictError(f"Catalog item '{normalized}' already exists.")

        max_item = await self.crud.get_max_sort_order_item()
        next_sort = (max_item.sort_order + 1) if max_item else 0

        item = SupplementCatalogItem(
            user_id=current_user_id(), key=normalized, label=label, sort_order=next_sort
        )
        self.crud.add(item)
        return await self.crud.commit_refresh(item)

    async def update_item(self, key: str, data: dict) -> SupplementCatalogItem:
        item = await self.crud.get_by_key(key)
        if not item:
            raise NotFoundError(f"Catalog item '{key}' not found.")

        for field, value in data.items():
            setattr(item, field, value)
        return await self.crud.commit_refresh(item)

    async def touch(self, keys: Iterable[str]) -> None:
        return await self.crud.touch(keys)
