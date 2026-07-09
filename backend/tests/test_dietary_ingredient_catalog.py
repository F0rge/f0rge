from __future__ import annotations

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ConflictError, NotFoundError
from app.schemas.dietary_ingredient import (
    AliasCreate,
    DietaryIngredientCreate,
    DietaryIngredientUpdate,
)
from app.services.dietary_ingredient_catalog import DietaryIngredientCatalogService

TEST_PIN = "1234"


@pytest.fixture
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(known_pin: str, async_client: AsyncClient) -> AsyncClient:
    """The house async_client, logged in via a real PIN login round-trip."""
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


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

    # remove_alias deletes the row directly and no longer mutates the parent's
    # warm in-memory collection, so drop the identity map to assert the DB truth.
    async_db.expunge_all()
    refreshed = await service.get(kimchi.id)
    assert refreshed.aliases == []


async def test_remove_alias_not_found_raises(async_db: AsyncSession) -> None:
    service = DietaryIngredientCatalogService(async_db)
    with pytest.raises(NotFoundError):
        await service.remove_alias(999999)



async def test_delete_alias_endpoint_returns_204(
    async_db: AsyncSession, authed_client: AsyncClient
) -> None:
    """DELETE /aliases/{id} against the real DB must be 204, not a 500.

    Regression for the MissingGreenlet: remove_alias used to reach through
    alias.ingredient.aliases, which lazy-loads in the async session when the
    alias is fetched cold by id. expunge_all() drops the warm identity map so
    the DELETE handler fetches the alias cold -- exactly like a real request,
    where the DELETE runs on its own fresh session. Without expunge the shared
    test session would keep the parent's aliases pre-loaded and hide the bug.
    """
    created = await authed_client.post(
        "/api/v1/dietary-ingredients", json={"canonical_name": "kimchi"}
    )
    assert created.status_code == 201
    ingredient_id = created.json()["id"]

    added = await authed_client.post(
        f"/api/v1/dietary-ingredients/{ingredient_id}/aliases",
        json={"alias": "fermented cabbage"},
    )
    assert added.status_code == 201
    alias_id = added.json()["id"]

    # Force the DELETE handler to fetch the alias cold, reproducing the
    # fresh-session flow that raised MissingGreenlet in production.
    async_db.expunge_all()

    deleted = await authed_client.delete(f"/api/v1/dietary-ingredients/aliases/{alias_id}")
    assert deleted.status_code == 204

    # No GET-by-id route exists; read the ingredient back off the list endpoint.
    listed = await authed_client.get("/api/v1/dietary-ingredients", params={"search": "kimchi"})
    assert listed.status_code == 200
    ingredient = next(i for i in listed.json() if i["id"] == ingredient_id)
    assert ingredient["aliases"] == []


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
