from __future__ import annotations

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user_provisioning import UserProvisioningCRUD
from f0rge_core.exceptions import ExternalServiceError
from app.models.diet_tag_catalog import DietTagCatalogItem
from app.seed_data import DEFAULT_DIET_TAGS
from f0rge_db.tenant import apply_session_user_id


async def is_user_provisioned(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """True when infrastructure catalogs were provisioned for this user."""
    await apply_session_user_id(db, user_id)
    return await UserProvisioningCRUD(db).is_infrastructure_provisioned(user_id)


async def provision_user_catalogs(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Seed infrastructure catalogs for a new user. Idempotent — safe to call twice."""
    if await is_user_provisioned(db, user_id):
        return

    await apply_session_user_id(db, user_id)
    now = datetime.datetime.utcnow()
    crud = UserProvisioningCRUD(db)

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
    ref_user_id = uuid.UUID(settings.default_storage_user_id)
    await _copy_reference_catalogs(crud, user_id)
    if ref_user_id != user_id:
        await _require_reference_catalog_copied(crud, user_id, ref_user_id)
    await crud.mark_infrastructure_provisioned(user_id)


async def repair_infrastructure_catalogs(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Re-copy reference catalogs when a user was marked provisioned with an empty copy."""
    if user_id == uuid.UUID(settings.default_storage_user_id):
        return

    await apply_session_user_id(db, user_id)
    crud = UserProvisioningCRUD(db)
    if not await crud.is_infrastructure_provisioned(user_id):
        await provision_user_catalogs(db, user_id)
        return

    if await crud.count_dietary_ingredients(user_id) > 0:
        return

    ref_user_id = uuid.UUID(settings.default_storage_user_id)
    await crud.copy_reference_catalogs(user_id, ref_user_id)
    await _require_reference_catalog_copied(crud, user_id, ref_user_id)


async def _require_reference_catalog_copied(
    crud: UserProvisioningCRUD,
    user_id: uuid.UUID,
    ref_user_id: uuid.UUID,
) -> None:
    await apply_session_user_id(crud.db, ref_user_id)
    ref_count = await crud.count_dietary_ingredients(ref_user_id)
    await apply_session_user_id(crud.db, user_id)
    user_count = await crud.count_dietary_ingredients(user_id)
    if ref_count > 0 and user_count == 0:
        raise ExternalServiceError("Reference catalog copy failed during signup")


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


async def _copy_reference_catalogs(crud: UserProvisioningCRUD, user_id: uuid.UUID) -> None:
    ref_user_id = uuid.UUID(settings.default_storage_user_id)
    if ref_user_id == user_id:
        return
    await crud.copy_reference_catalogs(user_id, ref_user_id)
