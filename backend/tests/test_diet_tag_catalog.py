from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.services import diet_tag_catalog as diet_tag_catalog_service


# ---------------------------------------------------------------------------
# create_item — key normalization preserves hyphens (the load-bearing test)
# ---------------------------------------------------------------------------


async def test_create_preserves_hyphenated_key(async_db: AsyncSession) -> None:
    """Regression: normalize_key MUST keep hyphens for diet tags.

    The migration seeds rows with hyphenated keys (high-histamine, high-fodmap)
    matching the entry.diet_risk CSV format and diet_flags.FLAG_VOCAB. If
    normalize_key were copied verbatim from supplement_catalog it would
    convert hyphens to underscores, silently splitting the catalog from the
    seed convention and breaking historical-entry chip rendering.
    """
    item = await diet_tag_catalog_service.create_item(async_db, "high-histamine", "High-histamine")
    assert item.key == "high-histamine"


async def test_create_normalizes_case_and_whitespace(async_db: AsyncSession) -> None:
    item = await diet_tag_catalog_service.create_item(
        async_db, "  High-Histamine  ", "High-histamine"
    )
    assert item.key == "high-histamine"


async def test_create_converts_underscore_to_hyphen(async_db: AsyncSession) -> None:
    """Underscore inputs are coerced to the hyphen convention."""
    item = await diet_tag_catalog_service.create_item(async_db, "high_histamine", "High-histamine")
    assert item.key == "high-histamine"


async def test_create_returns_persisted_item(async_db: AsyncSession) -> None:
    item = await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")
    assert item.id is not None
    assert item.label == "Gluten"


async def test_create_bad_key_raises_validation_error(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await diet_tag_catalog_service.create_item(async_db, "!!!", "Bad Key")


async def test_create_duplicate_active_raises_conflict(
    async_db: AsyncSession,
) -> None:
    await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")
    with pytest.raises(ConflictError):
        await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten 2")


async def test_create_duplicate_archived_unarchives_and_updates_label(
    async_db: AsyncSession,
) -> None:
    item = await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")
    await diet_tag_catalog_service.update_item(async_db, "gluten", {"archived": True})

    restored = await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "Gluten Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_archive_then_restore(async_db: AsyncSession) -> None:
    await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")

    archived = await diet_tag_catalog_service.update_item(async_db, "gluten", {"archived": True})
    assert archived.archived is True

    restored = await diet_tag_catalog_service.update_item(async_db, "gluten", {"archived": False})
    assert restored.archived is False


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await diet_tag_catalog_service.update_item(async_db, "nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_defaults_to_active_only(async_db: AsyncSession) -> None:
    await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")
    await diet_tag_catalog_service.create_item(async_db, "dairy", "Dairy")
    await diet_tag_catalog_service.update_item(async_db, "dairy", {"archived": True})

    active = await diet_tag_catalog_service.list_items(async_db)
    keys = [i.key for i in active]
    assert "gluten" in keys
    assert "dairy" not in keys


async def test_list_include_archived(async_db: AsyncSession) -> None:
    await diet_tag_catalog_service.create_item(async_db, "gluten", "Gluten")
    await diet_tag_catalog_service.create_item(async_db, "dairy", "Dairy")
    await diet_tag_catalog_service.update_item(async_db, "dairy", {"archived": True})

    all_items = await diet_tag_catalog_service.list_items(async_db, include_archived=True)
    keys = [i.key for i in all_items]
    assert "gluten" in keys
    assert "dairy" in keys
