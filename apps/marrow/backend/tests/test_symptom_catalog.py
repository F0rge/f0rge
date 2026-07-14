from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.symptom_catalog import SymptomCatalogService


# ---------------------------------------------------------------------------
# create_item
# ---------------------------------------------------------------------------


async def test_create_normalizes_key(async_db: AsyncSession) -> None:
    item = await SymptomCatalogService(async_db).create_item("VSS", "Visual Snow")
    assert item.id is not None
    assert item.key == "vss"
    assert item.label == "Visual Snow"


async def test_create_returns_201_equivalent(async_db: AsyncSession) -> None:
    """create_item returns the persisted item with an id."""
    item = await SymptomCatalogService(async_db).create_item("tinnitus", "Tinnitus")
    assert item.id is not None


async def test_create_bad_key_raises_validation_error(async_db: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await SymptomCatalogService(async_db).create_item("!!!", "Bad Key")


async def test_create_duplicate_active_raises_conflict(
    async_db: AsyncSession,
) -> None:
    await SymptomCatalogService(async_db).create_item("vss", "Visual Snow")
    with pytest.raises(ConflictError):
        await SymptomCatalogService(async_db).create_item("vss", "Visual Snow 2")


async def test_create_duplicate_archived_unarchives_and_updates_label(
    async_db: AsyncSession,
) -> None:
    """POST on an archived key un-archives it and updates the label (not 409)."""
    item = await SymptomCatalogService(async_db).create_item("vss", "Visual Snow")
    await SymptomCatalogService(async_db).update_item("vss", {"archived": True})

    restored = await SymptomCatalogService(async_db).create_item("vss", "VSS Updated")
    assert restored.id == item.id
    assert restored.archived is False
    assert restored.label == "VSS Updated"


# ---------------------------------------------------------------------------
# update_item
# ---------------------------------------------------------------------------


async def test_update_archive_then_restore(async_db: AsyncSession) -> None:
    await SymptomCatalogService(async_db).create_item("vss", "Visual Snow")

    archived = await SymptomCatalogService(async_db).update_item("vss", {"archived": True})
    assert archived.archived is True

    restored = await SymptomCatalogService(async_db).update_item("vss", {"archived": False})
    assert restored.archived is False


async def test_update_not_found_raises(async_db: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await SymptomCatalogService(async_db).update_item("nonexistent", {"archived": True})


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


async def test_list_defaults_to_active_only(async_db: AsyncSession) -> None:
    await SymptomCatalogService(async_db).create_item("vss", "Visual Snow")
    await SymptomCatalogService(async_db).create_item("tinnitus", "Tinnitus")
    await SymptomCatalogService(async_db).update_item("tinnitus", {"archived": True})

    active = await SymptomCatalogService(async_db).list_items()
    keys = [i.key for i in active]
    assert "vss" in keys
    assert "tinnitus" not in keys


async def test_list_include_archived(async_db: AsyncSession) -> None:
    await SymptomCatalogService(async_db).create_item("vss", "Visual Snow")
    await SymptomCatalogService(async_db).create_item("tinnitus", "Tinnitus")
    await SymptomCatalogService(async_db).update_item("tinnitus", {"archived": True})

    all_items = await SymptomCatalogService(async_db).list_items(include_archived=True)
    keys = [i.key for i in all_items]
    assert "vss" in keys
    assert "tinnitus" in keys


# ---------------------------------------------------------------------------
# Regression: create as a real (non-default) user
# ---------------------------------------------------------------------------


async def test_create_via_api_owned_by_authed_user(authed_client: AsyncClient) -> None:
    """A real signed-up (non-default) user must be able to add a custom symptom.

    Regression for the prod failure where a non-default user could not add
    "Diziness": create_item omitted user_id, so the row defaulted to
    default_storage_user_id and the RLS WITH CHECK policy rejected the insert
    for everyone else. The service-level tests above run as the default user,
    which masked it — this goes through the authed API path so the request runs
    under the signed-up user's app.user_id.
    """
    resp = await authed_client.post(
        "/api/v1/symptoms/catalog", json={"key": "diziness", "label": "Diziness"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["key"] == "diziness"

    # Ownership guard: the catalog list is scoped to the current user, so the
    # new symptom only appears if it was created with the right user_id.
    listed = await authed_client.get("/api/v1/symptoms/catalog")
    assert listed.status_code == 200
    assert any(item["key"] == "diziness" for item in listed.json())
