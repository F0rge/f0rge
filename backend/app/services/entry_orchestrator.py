from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.services.entries import EntryService, _build_response
from app.services.medication_catalog import MedicationCatalogService
from app.services.supplement_catalog import SupplementCatalogService
from app.services.symptom_catalog import SymptomCatalogService
from app.services.trackers import sync_seed_tracker_log_from_entry


class EntryOrchestrator:
    """Coordinates entry persistence with its collaborators (Rule 9.2 / 9.3).

    ``create_entry``/``update_entry`` used to mix Entry persistence with catalog
    touches and tracker-log sync inside ``EntryService`` itself. This pulls that
    coordination out one level: ``EntryService`` now only stages/commits the
    Entry row, and this class sequences the catalog touches + tracker sync
    around it on the shared session. Commit boundary is unchanged from before
    (catalog touches land in the same commit as the entry write) -- #225 will
    revisit transaction ownership, not this batch.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.entry_service = EntryService(db)

    async def _touch_catalogs(self, entry: Entry) -> None:
        supplement_keys = [s.strip() for s in (entry.supplements or "").split(",") if s.strip()]
        await SupplementCatalogService(self.db).touch(supplement_keys)
        await SymptomCatalogService(self.db).touch(list((entry.symptoms_json or {}).keys()))
        await MedicationCatalogService(self.db).touch(
            [m["key"] for m in entry.medications_json if m.get("key")]
        )

    async def create_entry(self, body: EntryCreate) -> EntryResponse:
        entry = await self.entry_service.stage_create(body)
        await self._touch_catalogs(entry)
        entry = await self.entry_service.commit_entry(entry)
        await sync_seed_tracker_log_from_entry(self.db, entry)
        return _build_response(entry)

    async def update_entry(self, date: datetime.date, body: EntryUpdate) -> EntryResponse:
        entry = await self.entry_service.stage_update(date, body)
        await self._touch_catalogs(entry)
        entry = await self.entry_service.commit_entry(entry)
        await sync_seed_tracker_log_from_entry(self.db, entry)
        return _build_response(entry)
