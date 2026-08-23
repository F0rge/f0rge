from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diet_tag_catalog import DietTagCatalogService
from app.services.entries import EntryService
from app.services.medication_catalog import MedicationCatalogService
from app.services.supplement_catalog import SupplementCatalogService
from app.services.symptom_catalog import SymptomCatalogService
from app.services.trackers import TrackerService
from app.utils.dates import local_today
from f0rge_core.exceptions import NotFoundError


class CacheWarmService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def warm(self) -> None:
        await SupplementCatalogService(self.db).list_items()
        await MedicationCatalogService(self.db).list_items()
        await DietTagCatalogService(self.db).list_items()
        await SymptomCatalogService(self.db).list_items()
        await TrackerService(self.db).list_trackers()

        today = local_today()
        try:
            await EntryService(self.db).get_entry(today)
        except NotFoundError:
            pass
