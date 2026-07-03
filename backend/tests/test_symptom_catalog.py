from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services import symptom_catalog as symptom_catalog_service


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


async def test_create_normalizes_key(async_db: AsyncSession) -> None:
    item = await symptom_catalog_service.create_item(async_db, "VSS", "Visual Snow")
    assert item.id is not None
    assert item.key == "vss"
    assert item.label == "Visual Snow"


async def test_create_returns_201_equivalent(async_db: AsyncSession) -> None:
    """create_item returns the persisted item with an id."""
    item = await symptom_catalog_service.create_item(async_db, "tinnitus", "Tinnitus")
    assert item.id is not None


async def test_create_bad_key_raises_validation_error(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await symptom_catalog_service.create_item(async_db, "!!!", "Bad Key")


async def test_create_duplicate_active_raises_conflict(
    async_db: AsyncSession,
) -> None:
    await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")
    with pytest.raises(ConflictError):
        await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow 2")


async def test_create_duplicate_archived_unarchives_and_updates_label(
    async_db: AsyncSession,
) -> None:
    """POST on an archived key un-archives it and updates the label (not 409)."""
    item = await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")
    await symptom_catalog_service.update_item(async_db, "vss", {"archived": True})

    restored = await symptom_catalog_service.create_item(async_db, "vss", "VSS Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "VSS Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_archive_then_restore(async_db: AsyncSession) -> None:
    await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")

    archived = await symptom_catalog_service.update_item(async_db, "vss", {"archived": True})
    assert archived.archived is True

    restored = await symptom_catalog_service.update_item(async_db, "vss", {"archived": False})
    assert restored.archived is False


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await symptom_catalog_service.update_item(async_db, "nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_defaults_to_active_only(async_db: AsyncSession) -> None:
    await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")
    await symptom_catalog_service.create_item(async_db, "tinnitus", "Tinnitus")
    await symptom_catalog_service.update_item(async_db, "tinnitus", {"archived": True})

    active = await symptom_catalog_service.list_items(async_db)
    keys = [i.key for i in active]
    assert "vss" in keys
    assert "tinnitus" not in keys


async def test_list_include_archived(async_db: AsyncSession) -> None:
    await symptom_catalog_service.create_item(async_db, "vss", "Visual Snow")
    await symptom_catalog_service.create_item(async_db, "tinnitus", "Tinnitus")
    await symptom_catalog_service.update_item(async_db, "tinnitus", {"archived": True})

    all_items = await symptom_catalog_service.list_items(async_db, include_archived=True)
    keys = [i.key for i in all_items]
    assert "vss" in keys
    assert "tinnitus" in keys
