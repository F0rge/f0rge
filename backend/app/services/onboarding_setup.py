from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog_suggestions import (
    curated_supplements,
    key_label_rows,
    medication_allowlist,
    supplement_allowlist,
    symptom_allowlist,
    tracker_allowlist,
    tracker_seed_by_name,
    tracker_suggestion_rows,
)
from app.crud.base import unit_of_work
from app.crud.user_provisioning import UserProvisioningCRUD
from app.exceptions import ValidationError
from app.models.medication_catalog import MedicationCatalogItem
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.tracker import Tracker
from app.seed_data import (
    BULK_MEDICATIONS,
    BULK_SUPPLEMENTS,
    DEFAULT_MEDICATIONS,
    DEFAULT_SYMPTOMS,
)
from app.schemas.onboarding import (
    CatalogSetupRequest,
    CatalogSetupResponse,
    CatalogSuggestionsResponse,
)
from app.tenant import current_user_id


class OnboardingSetupService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = UserProvisioningCRUD(db)

    def get_suggestions(self) -> CatalogSuggestionsResponse:
        return CatalogSuggestionsResponse(
            symptoms=key_label_rows(DEFAULT_SYMPTOMS),
            medications=key_label_rows(DEFAULT_MEDICATIONS),
            supplements=key_label_rows(curated_supplements()),
            trackers=tracker_suggestion_rows(),
            bulk_supplements=key_label_rows(BULK_SUPPLEMENTS),
            bulk_medications=key_label_rows(BULK_MEDICATIONS),
        )

    async def apply_catalog_setup(self, body: CatalogSetupRequest) -> CatalogSetupResponse:
        self._validate_keys("symptoms", body.symptoms, symptom_allowlist())
        self._validate_keys("medications", body.medications, medication_allowlist())
        self._validate_keys("supplements", body.supplements, supplement_allowlist())
        self._validate_keys("trackers", body.trackers, tracker_allowlist())

        now = datetime.datetime.utcnow()
        user_id = current_user_id()

        async with unit_of_work(self.db):
            symptoms_created = await self._insert_catalog_items(
                SymptomCatalogItem,
                "uq_symptom_catalog_user_id_key",
                user_id,
                body.symptoms,
                {key: label for key, label in DEFAULT_SYMPTOMS},
                now,
                include_usage_timestamps=True,
            )
            medications_created = await self._insert_catalog_items(
                MedicationCatalogItem,
                "uq_medication_catalog_user_id_key",
                user_id,
                body.medications,
                {key: label for key, label in DEFAULT_MEDICATIONS},
                now,
                include_usage_timestamps=True,
            )
            supplements_created = await self._insert_catalog_items(
                SupplementCatalogItem,
                "uq_supplement_catalog_user_id_key",
                user_id,
                body.supplements,
                {key: label for key, label in curated_supplements()},
                now,
                include_usage_timestamps=True,
            )
            trackers_created = await self._insert_trackers(user_id, body.trackers)

        return CatalogSetupResponse(
            symptoms_created=symptoms_created,
            medications_created=medications_created,
            supplements_created=supplements_created,
            trackers_created=trackers_created,
        )

    def _validate_keys(self, field: str, keys: list[str], allowlist: frozenset[str]) -> None:
        invalid = [key for key in keys if key not in allowlist]
        if invalid:
            raise ValidationError(f"Invalid {field} keys: {', '.join(invalid)}")

    async def _insert_catalog_items(
        self,
        model: type,
        constraint_name: str,
        user_id: object,
        keys: list[str],
        labels_by_key: dict[str, str],
        now: datetime.datetime,
        *,
        include_usage_timestamps: bool,
    ) -> int:
        if not keys:
            return 0

        values: list[dict[str, object]] = []
        for sort_order, key in enumerate(keys):
            row: dict[str, object] = {
                "user_id": user_id,
                "key": key,
                "label": labels_by_key[key],
                "archived": False,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            if include_usage_timestamps:
                row["first_used_at"] = None
                row["last_used_at"] = None
            values.append(row)

        return await self.crud.bulk_insert_ignore_conflict(model, values, constraint_name)

    async def _insert_trackers(self, user_id: object, names: list[str]) -> int:
        if not names:
            return 0

        seed_by_name = tracker_seed_by_name()
        values: list[dict[str, object]] = []
        for name in names:
            kind, icon, unit, position = seed_by_name[name]
            values.append(
                {
                    "user_id": user_id,
                    "name": name,
                    "kind": kind,
                    "icon": icon,
                    "unit": unit,
                    "position": position,
                    "archived": False,
                    "is_seed": True,
                }
            )

        return await self.crud.bulk_insert_ignore_conflict(Tracker, values, "uq_tracker_user_id_name")
