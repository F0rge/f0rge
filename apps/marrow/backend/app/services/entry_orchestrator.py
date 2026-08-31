from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import unit_of_work
from app.models.entry import Entry
from app.cache.invalidation import invalidate_user_insights_cache
from app.schemas.entry import EntryCreate, EntryResponse, EntryUpdate
from app.services.entries import EntryService, _build_response
from app.services.medication_catalog import MedicationCatalogService
from app.services.supplement_catalog import SupplementCatalogService
from app.services.symptom_catalog import SymptomCatalogService
from app.services.trackers import sync_seed_tracker_log_from_entry
from app.services.weather import attach_weather_for_date


class EntryOrchestrator:
    """Coordinates entry persistence with its collaborators (Rule 9.2 / 9.3;
    transaction boundary per Rule 6 / #225 6.4).

    ``create_entry``/``update_entry`` mix Entry persistence with catalog
    touches and tracker-log sync. All three used to land in *two* separate
    commits (entry write, then a second commit inside the tracker sync) --
    a tracker-sync failure left a half-written entry persisted. Now the whole
    sequence (stage entry -> touch catalogs -> stage tracker sync) runs inside
    one ``unit_of_work``: it all commits together or rolls back together.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.entry_service = EntryService(db)

    async def _touch_catalogs(self, entry: Entry) -> None:
        supplement_keys = [s.strip() for s in (entry.supplements or "").split(",") if s.strip()]
        await SupplementCatalogService(self.db).touch(supplement_keys)
        symptom_keys = set((entry.symptoms_json or {}).keys())
        for event in entry.symptom_events_json or []:
            key = event.get("key") if isinstance(event, dict) else None
            if key:
                symptom_keys.add(key)
        await SymptomCatalogService(self.db).touch(list(symptom_keys))
        await MedicationCatalogService(self.db).touch(
            [m["key"] for m in entry.medications_json if m.get("key")]
        )

    async def create_entry(self, body: EntryCreate) -> EntryResponse:
        async with unit_of_work(self.db):
            entry = await self.entry_service.stage_create(body)
            await self._touch_catalogs(entry)
            await sync_seed_tracker_log_from_entry(self.db, entry)
        user_id, entry_date = entry.user_id, entry.date
        await attach_weather_for_date(self.db, entry_date)
        await invalidate_user_insights_cache(user_id, entry_date)
        # Unlike every other write path, this one genuinely needs a refresh:
        # ``entry`` was *constructed*, never loaded via a SELECT, so the
        # mapper's ``lazy="selectin"`` companion query for ``photos`` (which
        # _build_response reads) never fired. Without this, the first bare
        # ``entry.photos`` access below is an implicit lazy-load outside the
        # asyncpg greenlet bridge -> ``MissingGreenlet``. ``refresh()`` reloads
        # it safely because it's awaited (#225 6.5's "keep it when in doubt").
        await self.db.refresh(entry)
        return await _build_response(self.db, entry)

    async def update_entry(self, date: datetime.date, body: EntryUpdate) -> EntryResponse:
        async with unit_of_work(self.db):
            entry = await self.entry_service.stage_update(date, body)
            await self._touch_catalogs(entry)
            await sync_seed_tracker_log_from_entry(self.db, entry)
        user_id, entry_date = entry.user_id, entry.date
        await attach_weather_for_date(self.db, entry_date)
        await invalidate_user_insights_cache(user_id, entry_date)
        return await _build_response(self.db, entry)
