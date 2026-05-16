from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.schemas.lab_marker import (
    LabMarkerCatalogCreate,
    MarkerHistoryPoint,
)


def _normalize_canonical(name: str) -> str:
    """Convert a raw name to lowercase underscored canonical form."""
    key = name.strip().lower()
    key = re.sub(r"[\s\-]+", "_", key)
    key = re.sub(r"[^a-z0-9_]", "", key)
    return key


class LabMarkerCatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(self, q: Optional[str], limit: int = 50) -> List[LabMarkerCatalog]:
        """Search catalog by canonical name, display name, or alias (ilike)."""
        stmt = select(LabMarkerCatalog)
        if q:
            pattern = f"%{q}%"
            alias_ids_stmt = (
                select(LabMarkerAlias.catalog_id)
                .where(LabMarkerAlias.alias.ilike(pattern))
                .subquery()
            )
            stmt = stmt.where(
                LabMarkerCatalog.canonical_name.ilike(pattern)
                | LabMarkerCatalog.display_name.ilike(pattern)
                | LabMarkerCatalog.id.in_(alias_ids_stmt)
            )
        stmt = stmt.order_by(LabMarkerCatalog.canonical_name).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_marker_history(self, canonical_name: str) -> List[MarkerHistoryPoint]:
        """Return time-ordered numeric history for a canonical marker name."""
        rows = (
            (
                await self.db.execute(
                    select(LabMarker)
                    .join(Lab, LabMarker.lab_id == Lab.id)
                    .where(
                        LabMarker.canonical_name == canonical_name,
                        LabMarker.value.isnot(None),
                    )
                    .order_by(Lab.lab_date.asc())
                )
            )
            .scalars()
            .all()
        )
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

    async def create_catalog_item(
        self, data: LabMarkerCatalogCreate
    ) -> LabMarkerCatalog:
        canonical = _normalize_canonical(data.canonical_name)
        existing = (
            await self.db.execute(
                select(LabMarkerCatalog).where(
                    LabMarkerCatalog.canonical_name == canonical
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"Catalog item with canonical_name={canonical!r} already exists."
            )
        item = LabMarkerCatalog(
            canonical_name=canonical,
            display_name=data.display_name,
            common_units=data.common_units,
            description=data.description,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def add_alias(
        self, catalog_id: int, alias: str, language: Optional[str]
    ) -> LabMarkerAlias:
        catalog = (
            await self.db.execute(
                select(LabMarkerCatalog).where(LabMarkerCatalog.id == catalog_id)
            )
        ).scalar_one_or_none()
        if catalog is None:
            raise NotFoundError(f"Catalog item {catalog_id} not found.")

        normalized = alias.strip().lower()
        existing = (
            await self.db.execute(
                select(LabMarkerAlias).where(LabMarkerAlias.alias == normalized)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                f"Alias {normalized!r} is already mapped to catalog item "
                f"{existing.catalog_id}."
            )
        alias_obj = LabMarkerAlias(
            catalog_id=catalog_id,
            alias=normalized,
            language=language,
        )
        self.db.add(alias_obj)
        await self.db.flush()
        await self.db.refresh(alias_obj)
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
        item = (
            await self.db.execute(
                select(LabMarkerCatalog).where(
                    LabMarkerCatalog.canonical_name == canonical
                )
            )
        ).scalar_one_or_none()
        if item is not None:
            return item

        # 2. Exact alias
        normalized_input = name.strip().lower()
        alias_row = (
            await self.db.execute(
                select(LabMarkerAlias).where(LabMarkerAlias.alias == normalized_input)
            )
        ).scalar_one_or_none()
        if alias_row is not None:
            return alias_row.catalog

        # 3. ilike canonical
        item = (
            await self.db.execute(
                select(LabMarkerCatalog).where(
                    LabMarkerCatalog.canonical_name.ilike(canonical)
                )
            )
        ).scalar_one_or_none()
        if item is not None:
            return item

        # 4. Create new
        item = LabMarkerCatalog(
            canonical_name=canonical,
            display_name=display_name,
            common_units=units or [],
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)

        if normalized_input != canonical:
            alias_obj = LabMarkerAlias(
                catalog_id=item.id,
                alias=normalized_input,
                language=None,
            )
            self.db.add(alias_obj)
            await self.db.flush()

        return item
