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
from app.seed_data import DEFAULT_DIET_TAGS
from app.crud.user_provisioning import UserProvisioningCRUD
from app.services.user_provisioning import (
    is_user_provisioned,
    provision_user_catalogs,
    repair_infrastructure_catalogs,
)
from app.sql.copy_reference_catalogs import COPY_USER_CATALOG_FROM_REFERENCE_SQL
from tests.helpers import signup_payload


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
        json=signup_payload(email, TEST_PASSWORD),
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


async def test_signup_seeds_infrastructure_only(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_id = await _signup_user(async_client)

    assert await _count_for_user(async_db, user_id, SupplementCatalogItem) == 0
    assert await _count_for_user(async_db, user_id, SymptomCatalogItem) == 0
    assert await _count_for_user(async_db, user_id, MedicationCatalogItem) == 0
    assert await _count_for_user(async_db, user_id, Tracker) == 0
    assert await _count_for_user(async_db, user_id, DietTagCatalogItem) == len(DEFAULT_DIET_TAGS)


async def _create_user(async_db: AsyncSession, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="test")
    async_db.add(user)
    await async_db.flush()
    return user.id


async def test_provision_user_catalogs_is_idempotent(async_db: AsyncSession) -> None:
    user_id = await _create_user(async_db, "idempotent@example.com")
    await _set_session_user_id(async_db, user_id)

    await provision_user_catalogs(async_db, user_id)
    first_tags = await _count_for_user(async_db, user_id, DietTagCatalogItem)

    await provision_user_catalogs(async_db, user_id)
    second_tags = await _count_for_user(async_db, user_id, DietTagCatalogItem)

    assert first_tags == len(DEFAULT_DIET_TAGS)
    assert second_tags == first_tags


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


async def test_is_user_provisioned_reflects_infrastructure_state(async_db: AsyncSession) -> None:
    user_id = await _create_user(async_db, "provisioned-check@example.com")
    assert await is_user_provisioned(async_db, user_id) is False
    await provision_user_catalogs(async_db, user_id)
    assert await is_user_provisioned(async_db, user_id) is True


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


def test_copy_function_does_not_declare_row_security_off() -> None:
    """Regression guard (migration 032): `row_security = off` does NOT bypass RLS
    for prod's non-BYPASSRLS `schema_admin` owner — it raises InsufficientPrivilege
    under FORCE RLS. The copy must instead rely on the `provisioner` service-role
    policy, so the function must NOT re-declare row_security while staying DEFINER."""
    assert "row_security" not in COPY_USER_CATALOG_FROM_REFERENCE_SQL
    assert "SECURITY DEFINER" in COPY_USER_CATALOG_FROM_REFERENCE_SQL


async def test_repair_infrastructure_catalogs_refills_empty_ingredients(
    async_db: AsyncSession,
) -> None:
    await _seed_leo_dietary_reference(async_db)
    user_id = await _create_user(async_db, "repair-me@example.com")
    await _set_session_user_id(async_db, user_id)
    crud = UserProvisioningCRUD(async_db)
    await crud.mark_infrastructure_provisioned(user_id)
    assert await _count_for_user(async_db, user_id, DietaryIngredient) == 0

    await repair_infrastructure_catalogs(async_db, user_id)

    assert await _count_for_user(async_db, user_id, DietaryIngredient) == 1
    assert await _count_for_user(async_db, user_id, IngredientAlias) == 1
