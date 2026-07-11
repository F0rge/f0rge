from __future__ import annotations

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.user_provisioning import UserProvisioningCRUD
from app.models.diet_tag_catalog import DietTagCatalogItem
from app.seed_data import DEFAULT_DIET_TAGS
from app.tenant import apply_session_user_id


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
    await _copy_reference_catalogs(crud, user_id)
    await crud.mark_infrastructure_provisioned(user_id)


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
