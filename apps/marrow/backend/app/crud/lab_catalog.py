from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_alias import LabMarkerAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from f0rge_db.tenant import owned_by_user


class LabMarkerCatalogCRUD(BaseCRUD):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def search(self, q: Optional[str], limit: int) -> List[LabMarkerCatalog]:
        """Search catalog by canonical name, display name, or alias (ilike)."""
        stmt = select(LabMarkerCatalog).where(owned_by_user(LabMarkerCatalog.user_id))
        if q:
            pattern = f"%{q}%"
            alias_ids_stmt = (
                select(LabMarkerAlias.catalog_id)
                .where(
                    owned_by_user(LabMarkerAlias.user_id),
                    LabMarkerAlias.alias.ilike(pattern),
                )
                .subquery()
            )
            stmt = stmt.where(
                LabMarkerCatalog.canonical_name.ilike(pattern)
                | LabMarkerCatalog.display_name.ilike(pattern)
                | LabMarkerCatalog.id.in_(alias_ids_stmt)
            )
        stmt = stmt.order_by(LabMarkerCatalog.canonical_name).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_marker_history_rows(self, canonical_name: str) -> List[LabMarker]:
        stmt = (
            select(LabMarker)
            .join(Lab, LabMarker.lab_id == Lab.id)
            .where(
                owned_by_user(LabMarker.user_id),
                owned_by_user(Lab.user_id),
                LabMarker.canonical_name == canonical_name,
                LabMarker.value.isnot(None),
            )
            .order_by(Lab.lab_date.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_canonical(self, canonical_name: str) -> Optional[LabMarkerCatalog]:
        stmt = select(LabMarkerCatalog).where(
            owned_by_user(LabMarkerCatalog.user_id),
            LabMarkerCatalog.canonical_name == canonical_name,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_canonical_ilike(self, canonical_name: str) -> Optional[LabMarkerCatalog]:
        stmt = select(LabMarkerCatalog).where(
            owned_by_user(LabMarkerCatalog.user_id),
            LabMarkerCatalog.canonical_name.ilike(canonical_name),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, catalog_id: int) -> Optional[LabMarkerCatalog]:
        stmt = select(LabMarkerCatalog).where(
            owned_by_user(LabMarkerCatalog.user_id), LabMarkerCatalog.id == catalog_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_alias(self, alias: str) -> Optional[LabMarkerAlias]:
        stmt = select(LabMarkerAlias).where(
            owned_by_user(LabMarkerAlias.user_id), LabMarkerAlias.alias == alias
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
