from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.schemas.dietary_ingredient import (
    AliasCreate,
    DietaryIngredientCreate,
    DietaryIngredientUpdate,
)
from app.services.dietary_ingredient_catalog import DietaryIngredientCatalogService


# ---------------------------------------------------------------------------
# create_item / get — round trip
# ---------------------------------------------------------------------------


async def test_create_and_get_round_trip(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    created = await service.create_item(
        DietaryIngredientCreate(
            canonical_name="  Kimchi  ", category="fermented", histamine_score=3
        )
    )
    assert created.canonical_name == "kimchi"
    assert created.category == "fermented"
    assert created.histamine_score == 3
    assert created.archived is False
    assert created.aliases == []

    fetched = await service.get(created.id)
    assert fetched.id == created.id
    assert fetched.canonical_name == "kimchi"


async def test_create_duplicate_canonical_name_raises_conflict(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))
    with pytest.raises(ConflictError):
        await service.create_item(DietaryIngredientCreate(canonical_name="Kimchi"))


async def test_create_archived_canonical_name_restores_and_updates(
    async_db: AsyncSession,
) -> None:
    service = DietaryIngredientCatalogService(async_db)
    created = await service.create_item(
        DietaryIngredientCreate(canonical_name="kimchi", category="fermented", histamine_score=3)
    )
    await service.set_archived(created.id, True)

    restored = await service.create_item(
        DietaryIngredientCreate(
            canonical_name=" Kimchi ",
            category="vegetables",
            histamine_score=1,
            contains_gluten=True,
            source_version="v2",
        )
    )

    assert restored.id == created.id
    assert restored.archived is False
    assert restored.canonical_name == "kimchi"
    assert restored.category == "vegetables"
    assert restored.histamine_score == 1
    assert restored.contains_gluten is True
    assert restored.source_version == "v2"


async def test_get_not_found_raises(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    with pytest.raises(NotFoundError):
        await service.get(999999)


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_a_field(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    created = await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))

    updated = await service.update_item(
        created.id, DietaryIngredientUpdate(histamine_score=2, category="fermented")
    )
    assert updated.histamine_score == 2
    assert updated.category == "fermented"


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    with pytest.raises(NotFoundError):
        await service.update_item(999999, DietaryIngredientUpdate(category="fermented"))


# ---------------------------------------------------------------------------
# archive round trip
# ---------------------------------------------------------------------------


async def test_archive_round_trip_via_list(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    kimchi = await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))
    await service.create_item(DietaryIngredientCreate(canonical_name="banana"))

    await service.set_archived(kimchi.id, True)

    active_only = await service.list_items()
    active_names = [i.canonical_name for i in active_only]
    assert "kimchi" not in active_names
    assert "banana" in active_names

    with_archived = await service.list_items(include_archived=True)
    all_names = [i.canonical_name for i in with_archived]
    assert "kimchi" in all_names
    assert "banana" in all_names

    restored = await service.set_archived(kimchi.id, False)
    assert restored.archived is False


# ---------------------------------------------------------------------------
# aliases
# ---------------------------------------------------------------------------


async def test_add_alias_twice_is_idempotent(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    kimchi = await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))

    first = await service.add_alias(kimchi.id, AliasCreate(alias="Fermented Cabbage"))
    second = await service.add_alias(kimchi.id, AliasCreate(alias="fermented cabbage"))

    assert first.id == second.id

    refreshed = await service.get(kimchi.id)
    assert len(refreshed.aliases) == 1
    assert refreshed.aliases[0].alias == "fermented cabbage"


async def test_remove_alias(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    kimchi = await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))
    alias = await service.add_alias(kimchi.id, AliasCreate(alias="fermented cabbage"))

    await service.remove_alias(alias.id)

    refreshed = await service.get(kimchi.id)
    assert refreshed.aliases == []


async def test_remove_alias_not_found_raises(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    with pytest.raises(NotFoundError):
        await service.remove_alias(999999)


# ---------------------------------------------------------------------------
# list_items search
# ---------------------------------------------------------------------------


async def test_list_items_search_filters(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    await service.create_item(DietaryIngredientCreate(canonical_name="kimchi"))
    await service.create_item(DietaryIngredientCreate(canonical_name="banana"))

    results = await service.list_items(search="kim")
    names = [i.canonical_name for i in results]
    assert names == ["kimchi"]
