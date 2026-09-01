from __future__ import annotations

import datetime
import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.location_bin import LocationBinCRUD
from app.models.location_bin import LocationBin, grid_bin_code, new_floor_bin
from app.schemas.location_bin import BinCreate, BinGridCreate, BinUpdate, LocationBinResponse
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def normalize_row_code(raw: str) -> str:
    value = raw.strip().upper()
    if not value or len(value) > 8:
        raise ValidationError("row_code must be 1–8 characters")
    return value


class LocationBinService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = LocationBinCRUD(db)
        self.location_crud = LocationCRUD(db)

    async def list(self, location_id: uuid.UUID) -> list[LocationBinResponse]:
        await self._get_location_or_404(location_id)
        return [self._to_response(row) for row in await self.crud.list_by_location(location_id)]

    async def create(self, location_id: uuid.UUID, data: BinCreate) -> LocationBinResponse:
        location = await self._get_location_or_404(location_id)
        if location.is_archived:
            raise ConflictError("Cannot add bins to archived location")

        row_code = normalize_row_code(data.row_code)
        code = grid_bin_code(row_code, data.bay, data.level)
        await self._assert_slot_available(location_id, row_code, data.bay, data.level, code)

        bin_row = LocationBin(
            location_id=location_id,
            code=code,
            row_code=row_code,
            bay=data.bay,
            level=data.level,
            is_default=False,
            is_archived=False,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(bin_row)
        except IntegrityError as exc:
            raise ConflictError("A bin already exists at this location") from exc
        reloaded = await self.crud.get_by_id(bin_row.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def generate_grid(
        self,
        location_id: uuid.UUID,
        data: BinGridCreate,
    ) -> list[LocationBinResponse]:
        location = await self._get_location_or_404(location_id)
        if location.is_archived:
            raise ConflictError("Cannot add bins to archived location")

        rows: list[str] = []
        seen: set[str] = set()
        for raw in data.rows:
            row_code = normalize_row_code(raw)
            if row_code in seen:
                continue
            seen.add(row_code)
            rows.append(row_code)

        try:
            async with unit_of_work(self.db):
                for row_code in rows:
                    for bay in range(1, data.bays + 1):
                        for level in range(1, data.levels + 1):
                            existing = await self.crud.get_by_slot(
                                location_id,
                                row_code,
                                bay,
                                level,
                            )
                            if existing is not None:
                                continue
                            await self.crud.add_and_flush(
                                LocationBin(
                                    location_id=location_id,
                                    code=grid_bin_code(row_code, bay, level),
                                    row_code=row_code,
                                    bay=bay,
                                    level=level,
                                    is_default=False,
                                    is_archived=False,
                                )
                            )
        except IntegrityError as exc:
            raise ConflictError("A bin already exists at this location") from exc
        return await self.list(location_id)

    async def update(
        self,
        location_id: uuid.UUID,
        bin_id: uuid.UUID,
        data: BinUpdate,
    ) -> LocationBinResponse:
        await self._get_location_or_404(location_id)
        bin_row = await self._get_bin_or_404(location_id, bin_id)

        if data.is_archived is False:
            bin_row.is_archived = False
            bin_row.archived_at = None

        if data.is_archived is True:
            await self._assert_can_archive(bin_row)
            bin_row.is_archived = True
            bin_row.archived_at = datetime.datetime.utcnow()
            bin_row.is_default = False

        if data.is_default is False and bin_row.is_default:
            raise ConflictError("Cannot clear default without assigning another")

        if data.is_default is True:
            if bin_row.is_archived:
                raise ConflictError("Archived bin cannot become default")
            await self.crud.clear_default(location_id, bin_row.id)
            bin_row.is_default = True

        try:
            async with unit_of_work(self.db):
                await self.crud.flush()
        except IntegrityError as exc:
            raise ConflictError("A bin already exists at this location") from exc
        reloaded = await self.crud.get_by_id(bin_row.id)
        assert reloaded is not None
        return self._to_response(reloaded)

    async def ensure_default_bin(self, location_id: uuid.UUID) -> LocationBin:
        existing = await self.crud.get_active_default(location_id)
        if existing is not None:
            return existing
        active = await self.crud.list_active(location_id)
        if active:
            raise ConflictError("Location has no default bin")
        bin_row = new_floor_bin(location_id)
        await self.crud.add_and_flush(bin_row)
        return bin_row

    async def resolve_for_movement(
        self,
        location_id: uuid.UUID,
        bin_id: Optional[uuid.UUID],
        *,
        incoming: bool,
    ) -> LocationBin:
        if bin_id is None:
            return await self.ensure_default_bin(location_id)
        bin_row = await self.crud.get_by_id(bin_id)
        if bin_row is None or bin_row.location_id != location_id:
            raise NotFoundError("Bin not found")
        if incoming and bin_row.is_archived:
            raise ConflictError("Cannot receive into archived bin")
        return bin_row

    async def _get_location_or_404(self, location_id: uuid.UUID):
        location = await self.location_crud.get_by_id(location_id)
        if location is None:
            raise NotFoundError("Location not found")
        return location

    async def _get_bin_or_404(self, location_id: uuid.UUID, bin_id: uuid.UUID) -> LocationBin:
        bin_row = await self.crud.get_by_id(bin_id)
        if bin_row is None or bin_row.location_id != location_id:
            raise NotFoundError("Bin not found")
        return bin_row

    async def _assert_slot_available(
        self,
        location_id: uuid.UUID,
        row_code: str,
        bay: int,
        level: int,
        code: str,
    ) -> None:
        slot = await self.crud.get_by_slot(location_id, row_code, bay, level)
        if slot is not None and not slot.is_archived:
            raise ConflictError("A bin already exists at this location")
        by_code = await self.crud.get_active_by_code(location_id, code)
        if by_code is not None:
            raise ConflictError("A bin already exists at this location")

    async def _assert_can_archive(self, bin_row: LocationBin) -> None:
        if not bin_row.is_default or bin_row.is_archived:
            return
        raise ConflictError("Cannot archive the default bin without assigning another")

    @staticmethod
    def _to_response(row: LocationBin) -> LocationBinResponse:
        return LocationBinResponse.model_validate(row)
