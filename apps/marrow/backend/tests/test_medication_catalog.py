from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.medication_catalog import MedicationCatalogService


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


async def test_create_normalizes_case_and_whitespace(async_db: AsyncSession) -> None:
    item = await MedicationCatalogService(async_db).create_item("  Ibuprofen  ", "Ibuprofen")
    assert item.key == "ibuprofen"


async def test_create_converts_hyphen_to_underscore(async_db: AsyncSession) -> None:
    item = await MedicationCatalogService(async_db).create_item("vitamin-c", "Vitamin C")
    assert item.key == "vitamin_c"


async def test_create_returns_persisted_item(async_db: AsyncSession) -> None:
    item = await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")
    assert item.id is not None
    assert item.label == "Aspirin"


async def test_create_bad_key_raises_validation_error(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await MedicationCatalogService(async_db).create_item("!!!", "Bad Key")


async def test_create_duplicate_active_raises_conflict(async_db: AsyncSession) -> None:
    await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")
    with pytest.raises(ConflictError):
        await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin 2")


async def test_create_duplicate_archived_unarchives_and_updates_label(
    async_db: AsyncSession,
) -> None:
    item = await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")
    await MedicationCatalogService(async_db).update_item("aspirin", {"archived": True})

    restored = await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "Aspirin Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_archive_then_restore(async_db: AsyncSession) -> None:
    await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")

    archived = await MedicationCatalogService(async_db).update_item("aspirin", {"archived": True})
    assert archived.archived is True

    restored = await MedicationCatalogService(async_db).update_item("aspirin", {"archived": False})
    assert restored.archived is False


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await MedicationCatalogService(async_db).update_item("nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_defaults_to_active_only(async_db: AsyncSession) -> None:
    await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")
    await MedicationCatalogService(async_db).create_item("imodium", "Imodium")
    await MedicationCatalogService(async_db).update_item("imodium", {"archived": True})

    active = await MedicationCatalogService(async_db).list_items()
    keys = [i.key for i in active]
    assert "aspirin" in keys
    assert "imodium" not in keys


async def test_list_include_archived(async_db: AsyncSession) -> None:
    await MedicationCatalogService(async_db).create_item("aspirin", "Aspirin")
    await MedicationCatalogService(async_db).create_item("imodium", "Imodium")
    await MedicationCatalogService(async_db).update_item("imodium", {"archived": True})

    all_items = await MedicationCatalogService(async_db).list_items(include_archived=True)
    keys = [i.key for i in all_items]
    assert "aspirin" in keys
    assert "imodium" in keys
