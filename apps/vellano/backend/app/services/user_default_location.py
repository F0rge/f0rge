from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.services.locations import LocationSeedService
from f0rge_core.exceptions import NotFoundError, ValidationError

BEDFORDVIEW_DEFAULT = LocationSeedService.SEED_ROWS[1]


async def bedfordview_default_location_id(db: AsyncSession) -> Optional[uuid.UUID]:
    name, location_type = BEDFORDVIEW_DEFAULT
    location = await LocationCRUD(db).get_active_by_name_and_type(name, location_type)
    if location is None:
        return None
    return location.id


async def resolve_writable_default_location_id(
    db: AsyncSession,
    location_id: Optional[uuid.UUID],
) -> Optional[uuid.UUID]:
    if location_id is None:
        return None
    location = await LocationCRUD(db).get_by_id(location_id)
    if location is None:
        raise NotFoundError("Location not found")
    if location.is_archived:
        raise ValidationError("Location is archived")
    return location_id
