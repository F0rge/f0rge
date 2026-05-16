from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy.orm import Session

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
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(self, q: Optional[str], limit: int = 50) -> List[LabMarkerCatalog]:
        """Search catalog by canonical name, display name, or alias (ilike)."""
        query = self.db.query(LabMarkerCatalog)
        if q:
            pattern = f"%{q}%"
            alias_ids = (
                self.db.query(LabMarkerAlias.catalog_id)
                .filter(LabMarkerAlias.alias.ilike(pattern))
                .subquery()
            )
            query = query.filter(
                LabMarkerCatalog.canonical_name.ilike(pattern)
                | LabMarkerCatalog.display_name.ilike(pattern)
                | LabMarkerCatalog.id.in_(alias_ids)
            )
        return query.order_by(LabMarkerCatalog.canonical_name).limit(limit).all()

    def get_marker_history(self, canonical_name: str) -> List[MarkerHistoryPoint]:
        """Return time-ordered numeric history for a canonical marker name."""
        rows = (
            self.db.query(LabMarker)
            .join(Lab, LabMarker.lab_id == Lab.id)
            .filter(
                LabMarker.canonical_name == canonical_name,
                LabMarker.value.isnot(None),
            )
            .order_by(Lab.lab_date.asc())
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

    def create_catalog_item(self, data: LabMarkerCatalogCreate) -> LabMarkerCatalog:
        canonical = _normalize_canonical(data.canonical_name)
        existing = (
            self.db.query(LabMarkerCatalog)
            .filter(LabMarkerCatalog.canonical_name == canonical)
            .first()
        )
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
        self.db.flush()
        self.db.refresh(item)
        return item

    def add_alias(
        self, catalog_id: int, alias: str, language: Optional[str]
    ) -> LabMarkerAlias:
        catalog = (
            self.db.query(LabMarkerCatalog)
            .filter(LabMarkerCatalog.id == catalog_id)
            .first()
        )
        if catalog is None:
            raise NotFoundError(f"Catalog item {catalog_id} not found.")

        normalized = alias.strip().lower()
        existing = (
            self.db.query(LabMarkerAlias)
            .filter(LabMarkerAlias.alias == normalized)
            .first()
        )
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
        self.db.flush()
        self.db.refresh(alias_obj)
        return alias_obj

    def resolve_or_create(
        self,
        name: str,
        display_name: str,
        units: Optional[List[str]] = None,
    ) -> LabMarkerCatalog:
        """Find or create a catalog entry for the given marker name.

        Lookup chain (stops at first match):
        1. Exact canonical match.
        2. Exact alias match (lowercased input).
        3. Case-insensitive (ilike) canonical match.
        4. Create new entry and register input as an alias if it differs.
        """
        canonical = _normalize_canonical(name)

        # 1. Exact canonical
        item = (
            self.db.query(LabMarkerCatalog)
            .filter(LabMarkerCatalog.canonical_name == canonical)
            .first()
        )
        if item is not None:
            return item

        # 2. Exact alias
        normalized_input = name.strip().lower()
        alias_row = (
            self.db.query(LabMarkerAlias)
            .filter(LabMarkerAlias.alias == normalized_input)
            .first()
        )
        if alias_row is not None:
            return alias_row.catalog

        # 3. ilike canonical
        item = (
            self.db.query(LabMarkerCatalog)
            .filter(LabMarkerCatalog.canonical_name.ilike(canonical))
            .first()
        )
        if item is not None:
            return item

        # 4. Create new
        item = LabMarkerCatalog(
            canonical_name=canonical,
            display_name=display_name,
            common_units=units or [],
        )
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)

        # Register the original input as an alias when it differs from canonical.
        if normalized_input != canonical:
            alias_obj = LabMarkerAlias(
                catalog_id=item.id,
                alias=normalized_input,
                language=None,
            )
            self.db.add(alias_obj)
            self.db.flush()

        return item
