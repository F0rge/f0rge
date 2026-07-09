from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.diet_tag_catalog import DietTagCatalogItem
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.models.medication_catalog import MedicationCatalogItem
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.tracker import Tracker
from app.models.user import User
from app.seed_data import (
    BULK_MEDICATIONS,
    BULK_SUPPLEMENTS,
    DEFAULT_DIET_TAGS,
    DEFAULT_MEDICATIONS,
    DEFAULT_SYMPTOMS,
    DEFAULT_SUPPLEMENTS,
    DEFAULT_TRACKERS,
    SPLIT_VITAMIN_D_K2,
)
from app.services.user_provisioning import is_user_provisioned, provision_user_catalogs


async def _set_session_user_id(async_db: AsyncSession, user_id: uuid.UUID) -> None:
    await async_db.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


TEST_EMAIL = "provision-test@example.com"
TEST_PASSWORD = "test-password-12"


async def _signup_user(async_client: AsyncClient, email: str = TEST_EMAIL) -> uuid.UUID:
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["user_id"])


async def _count_for_user(
    async_db: AsyncSession,
    user_id: uuid.UUID,
    model: type,
) -> int:
    await _set_session_user_id(async_db, user_id)
    user_column = getattr(model, "user_id")
    return (
        await async_db.execute(
            select(func.count()).select_from(model).where(user_column == user_id)
        )
    ).scalar_one()


async def _seed_leo_dietary_reference(async_db: AsyncSession) -> None:
    leo_id = uuid.UUID(settings.default_storage_user_id)
    await _set_session_user_id(async_db, leo_id)
    async_db.add(
        DietaryIngredient(
            user_id=leo_id,
            canonical_name="kimchi",
            category="fermented",
            histamine_score=3,
            source="manual",
        )
    )
    async_db.add(
        IngredientAlias(
            user_id=leo_id,
            alias="kimchee",
            canonical_name="kimchi",
            language="en",
        )
    )
    await async_db.flush()


async def test_signup_seeds_default_catalogs(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_id = await _signup_user(async_client)

    expected_supplements = (
        len(DEFAULT_SUPPLEMENTS) + len(SPLIT_VITAMIN_D_K2) + len(BULK_SUPPLEMENTS)
    )
    expected_medications = len(DEFAULT_MEDICATIONS) + len(BULK_MEDICATIONS)

    assert await _count_for_user(async_db, user_id, SupplementCatalogItem) == expected_supplements
    assert await _count_for_user(async_db, user_id, SymptomCatalogItem) == len(DEFAULT_SYMPTOMS)
    assert await _count_for_user(async_db, user_id, MedicationCatalogItem) == expected_medications
    assert await _count_for_user(async_db, user_id, DietTagCatalogItem) == len(DEFAULT_DIET_TAGS)
    assert await _count_for_user(async_db, user_id, Tracker) == len(DEFAULT_TRACKERS)


async def _create_user(async_db: AsyncSession, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="test")
    async_db.add(user)
    await async_db.flush()
    return user.id


async def test_provision_user_catalogs_is_idempotent(async_db: AsyncSession) -> None:
    user_id = await _create_user(async_db, "idempotent@example.com")
    await _set_session_user_id(async_db, user_id)

    await provision_user_catalogs(async_db, user_id)
    first_count = await _count_for_user(async_db, user_id, SupplementCatalogItem)

    await provision_user_catalogs(async_db, user_id)
    second_count = await _count_for_user(async_db, user_id, SupplementCatalogItem)

    assert first_count > 0
    assert second_count == first_count


async def test_signup_does_not_change_leo_catalogs(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    leo_id = uuid.UUID(settings.default_storage_user_id)
    await _set_session_user_id(async_db, leo_id)
    async_db.add(
        SupplementCatalogItem(
            user_id=leo_id,
            key="leo_custom",
            label="Leo Custom",
            archived=False,
            sort_order=999,
        )
    )
    await async_db.flush()
    leo_before = await _count_for_user(async_db, leo_id, SupplementCatalogItem)

    await _signup_user(async_client, email="other-user@example.com")

    leo_after = await _count_for_user(async_db, leo_id, SupplementCatalogItem)
    assert leo_after == leo_before


async def test_signup_copies_dietary_reference_catalog(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    await _seed_leo_dietary_reference(async_db)
    user_id = await _signup_user(async_client)

    assert await _count_for_user(async_db, user_id, DietaryIngredient) == 1
    assert await _count_for_user(async_db, user_id, IngredientAlias) == 1


async def test_is_user_provisioned_reflects_seeded_state(async_db: AsyncSession) -> None:
    user_id = await _create_user(async_db, "provisioned-check@example.com")
    assert await is_user_provisioned(async_db, user_id) is False
    await provision_user_catalogs(async_db, user_id)
    assert await is_user_provisioned(async_db, user_id) is True


async def test_signup_seeds_active_supplements_for_daily_picker(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_id = await _signup_user(async_client)
    await _set_session_user_id(async_db, user_id)
    active = (
        (
            await async_db.execute(
                select(SupplementCatalogItem.key).where(SupplementCatalogItem.archived.is_(False))
            )
        )
        .scalars()
        .all()
    )
    assert "nac" in active
    assert "vitamin_d" in active
    assert "vitamin_k2" in active
    assert "vitamin_d_k2" not in active


async def test_signup_copies_lab_marker_catalog_from_reference(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    leo_id = uuid.UUID(settings.default_storage_user_id)
    await _set_session_user_id(async_db, leo_id)
    async_db.add(
        LabMarkerCatalog(
            user_id=leo_id,
            canonical_name="hemoglobin",
            display_name="Hemoglobin",
            common_units=["g/dL"],
        )
    )
    await async_db.flush()

    user_id = await _signup_user(async_client, email="lab-user@example.com")
    assert await _count_for_user(async_db, user_id, LabMarkerCatalog) == 1
