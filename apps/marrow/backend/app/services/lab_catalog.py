from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.lab_catalog import LabMarkerCatalogCRUD
from f0rge_core.exceptions import ConflictError, NotFoundError
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.schemas.lab_marker import (
    LabMarkerCatalogCreate,
    MarkerHistoryPoint,
)
from f0rge_db.tenant import current_user_id

CATALOG_SEARCH_LIMIT = 50


def _normalize_canonical(name: str) -> str:
    """Convert a raw name to lowercase underscored canonical form."""
    key = name.strip().lower()
    key = re.sub(r"[\s\-]+", "_", key)
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


class LabMarkerCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LabMarkerCatalogCRUD(db)

    async def search(
        self, q: Optional[str], limit: int = CATALOG_SEARCH_LIMIT
    ) -> List[LabMarkerCatalog]:
        return await self.crud.search(q, limit)

    async def get_marker_history(self, canonical_name: str) -> List[MarkerHistoryPoint]:
        """Return time-ordered numeric history for a canonical marker name."""
        rows = await self.crud.list_marker_history_rows(canonical_name)
        return [
            MarkerHistoryPoint(
                lab_date=row.lab.lab_date,
                value=row.value,
                value_text=row.value_text,
                unit=row.unit,
                ref_low=row.ref_low,
                ref_high=row.ref_high,
                flag=row.flag,
            )
            for row in rows
        ]

    async def create_catalog_item(self, data: LabMarkerCatalogCreate) -> LabMarkerCatalog:
        canonical = _normalize_canonical(data.canonical_name)
        existing = await self.crud.get_by_canonical(canonical)
        if existing is not None:
            raise ConflictError(f"Catalog item with canonical_name={canonical!r} already exists.")
        item = LabMarkerCatalog(
            user_id=current_user_id(),
            canonical_name=canonical,
            display_name=data.display_name,
            common_units=data.common_units,
            description=data.description,
        )
        await self.crud.add_and_flush(item)
        return item

    async def add_alias(
        self, catalog_id: int, alias: str, language: Optional[str]
    ) -> LabMarkerAlias:
        catalog = await self.crud.get_by_id(catalog_id)
        if catalog is None:
            raise NotFoundError(f"Catalog item {catalog_id} not found.")

        normalized = alias.strip().lower()
        existing = await self.crud.get_alias(normalized)
        if existing is not None:
            raise ConflictError(
                f"Alias {normalized!r} is already mapped to catalog item {existing.catalog_id}."
            )
        alias_obj = LabMarkerAlias(
            user_id=catalog.user_id,
            catalog_id=catalog_id,
            alias=normalized,
            language=language,
        )
        await self.crud.add_and_flush(alias_obj)
        return alias_obj

    async def resolve_or_create(
        self,
        name: str,
        display_name: str,
        units: Optional[List[str]] = None,
    ) -> LabMarkerCatalog:
        """Find or create a catalog entry for the given marker name."""
        canonical = _normalize_canonical(name)

        # 1. Exact canonical
        item = await self.crud.get_by_canonical(canonical)
        if item is not None:
            return item

        # 2. Exact alias
        normalized_input = name.strip().lower()
        alias_row = await self.crud.get_alias(normalized_input)
        if alias_row is not None:
            return alias_row.catalog

        # 3. ilike canonical
        item = await self.crud.get_by_canonical_ilike(canonical)
        if item is not None:
            return item

        # 4. Create new
        item = LabMarkerCatalog(
            user_id=current_user_id(),
            canonical_name=canonical,
            display_name=display_name,
            common_units=units or [],
        )
        await self.crud.add_and_flush(item)

        if normalized_input != canonical:
            alias_obj = LabMarkerAlias(
                user_id=item.user_id,
                catalog_id=item.id,
                alias=normalized_input,
                language=None,
            )
            await self.crud.add_and_flush(alias_obj)

        return item
