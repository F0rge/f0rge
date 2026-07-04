from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services import medication_catalog as medication_catalog_service


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


async def test_create_normalizes_case_and_whitespace(async_db: AsyncSession) -> None:
    item = await medication_catalog_service.create_item(async_db, "  Ibuprofen  ", "Ibuprofen")
    assert item.key == "ibuprofen"


async def test_create_converts_hyphen_to_underscore(async_db: AsyncSession) -> None:
    item = await medication_catalog_service.create_item(async_db, "vitamin-c", "Vitamin C")
    assert item.key == "vitamin_c"


async def test_create_returns_persisted_item(async_db: AsyncSession) -> None:
    item = await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")
    assert item.id is not None
    assert item.label == "Aspirin"


async def test_create_bad_key_raises_validation_error(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await medication_catalog_service.create_item(async_db, "!!!", "Bad Key")


async def test_create_duplicate_active_raises_conflict(async_db: AsyncSession) -> None:
    await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")
    with pytest.raises(ConflictError):
        await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin 2")


async def test_create_duplicate_archived_unarchives_and_updates_label(
    async_db: AsyncSession,
) -> None:
    item = await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")
    await medication_catalog_service.update_item(async_db, "aspirin", {"archived": True})

    restored = await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "Aspirin Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_archive_then_restore(async_db: AsyncSession) -> None:
    await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")

    archived = await medication_catalog_service.update_item(async_db, "aspirin", {"archived": True})
    assert archived.archived is True

    restored = await medication_catalog_service.update_item(
        async_db, "aspirin", {"archived": False}
    )
    assert restored.archived is False


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await medication_catalog_service.update_item(async_db, "nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_defaults_to_active_only(async_db: AsyncSession) -> None:
    await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")
    await medication_catalog_service.create_item(async_db, "imodium", "Imodium")
    await medication_catalog_service.update_item(async_db, "imodium", {"archived": True})

    active = await medication_catalog_service.list_items(async_db)
    keys = [i.key for i in active]
    assert "aspirin" in keys
    assert "imodium" not in keys


async def test_list_include_archived(async_db: AsyncSession) -> None:
    await medication_catalog_service.create_item(async_db, "aspirin", "Aspirin")
    await medication_catalog_service.create_item(async_db, "imodium", "Imodium")
    await medication_catalog_service.update_item(async_db, "imodium", {"archived": True})

    all_items = await medication_catalog_service.list_items(async_db, include_archived=True)
    keys = [i.key for i in all_items]
    assert "aspirin" in keys
    assert "imodium" in keys
