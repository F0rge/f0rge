from __future__ import annotations

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user_provisioning import UserProvisioningCRUD
from app.models.diet_tag_catalog import DietTagCatalogItem
from app.models.medication_catalog import MedicationCatalogItem
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.tracker import Tracker
from app.seed_data import (
    DEFAULT_DIET_TAGS,
    DEFAULT_SYMPTOMS,
    DEFAULT_TRACKERS,
    medication_seed_rows,
    supplement_seed_rows,
)
from app.tenant import apply_session_user_id


async def is_user_provisioned(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """True when the user already has seeded supplement catalog rows."""
    await apply_session_user_id(db, user_id)
    count = await UserProvisioningCRUD(db).count_supplement_catalog_items()
    return count > 0


async def provision_user_catalogs(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Seed default catalogs for a new user. Idempotent — safe to call twice."""
    if await is_user_provisioned(db, user_id):
        return

    await apply_session_user_id(db, user_id)
    now = datetime.datetime.utcnow()
    crud = UserProvisioningCRUD(db)

    await _insert_key_label_catalog(
        crud,
        user_id,
        SupplementCatalogItem,
        "uq_supplement_catalog_user_id_key",
        supplement_seed_rows(),
        now,
        include_usage_timestamps=True,
    )
    await _insert_key_label_catalog(
        crud,
        user_id,
        SymptomCatalogItem,
        "uq_symptom_catalog_user_id_key",
        [
            (key, label, False, sort_order)
            for sort_order, (key, label) in enumerate(DEFAULT_SYMPTOMS)
        ],
        now,
        include_usage_timestamps=True,
    )
    await _insert_key_label_catalog(
        crud,
        user_id,
        MedicationCatalogItem,
        "uq_medication_catalog_user_id_key",
        medication_seed_rows(),
        now,
        include_usage_timestamps=True,
    )
    await _insert_key_label_catalog(
        crud,
        user_id,
        DietTagCatalogItem,
        "uq_diet_tag_catalog_user_id_key",
        [
            (key, label, False, sort_order)
            for sort_order, (key, label) in enumerate(DEFAULT_DIET_TAGS)
        ],
        now,
        include_usage_timestamps=False,
    )
    await _insert_trackers(crud, user_id)
    await _copy_reference_catalogs(crud, user_id)


async def _insert_key_label_catalog(
    crud: UserProvisioningCRUD,
    user_id: uuid.UUID,
    model: type,
    constraint_name: str,
    rows: list[tuple[str, str, bool, int]],
    now: datetime.datetime,
    *,
    include_usage_timestamps: bool,
) -> None:
    values: list[dict[str, object]] = []
    for key, label, archived, sort_order in rows:
        row: dict[str, object] = {
            "user_id": user_id,
            "key": key,
            "label": label,
            "archived": archived,
            "sort_order": sort_order,
            "created_at": now,
            "updated_at": now,
        }
        if include_usage_timestamps:
            row["first_used_at"] = None
            row["last_used_at"] = None
        values.append(row)

    await crud.bulk_insert_ignore_conflict(model, values, constraint_name)


async def _insert_trackers(crud: UserProvisioningCRUD, user_id: uuid.UUID) -> None:
    values = [
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
        for name, kind, icon, unit, position in DEFAULT_TRACKERS
    ]
    await crud.bulk_insert_ignore_conflict(Tracker, values, "uq_tracker_user_id_name")


async def _copy_reference_catalogs(crud: UserProvisioningCRUD, user_id: uuid.UUID) -> None:
    ref_user_id = uuid.UUID(settings.default_storage_user_id)
    if ref_user_id == user_id:
        return
    await crud.copy_reference_catalogs(user_id, ref_user_id)
