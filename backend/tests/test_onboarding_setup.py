from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplement_catalog import SupplementCatalogItem
from app.models.symptom_catalog import SymptomCatalogItem
from app.models.tracker import Tracker


async def _set_session_user_id(async_db: AsyncSession, user_id: uuid.UUID) -> None:
    await async_db.execute(
        sa.text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


async def _signup(async_client: AsyncClient, email: str) -> uuid.UUID:
    resp = await async_client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "test-password-12"},
    )
    assert resp.status_code == 200
    return uuid.UUID(resp.json()["user_id"])


async def test_catalog_suggestions_returns_curated_lists(async_client: AsyncClient) -> None:
    await _signup(async_client, "suggestions@example.com")

    resp = await async_client.get("/api/v1/catalog/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["symptoms"]) == 7
    assert len(data["medications"]) == 6
    assert any(item["key"] == "vitamin_d" for item in data["supplements"])
    assert all(item["key"] != "vitamin_d_k2" for item in data["supplements"])
    assert len(data["trackers"]) == 4
    assert len(data["bulk_supplements"]) > 50
    assert len(data["bulk_medications"]) > 50


async def test_catalog_setup_creates_selected_items(
    async_client: AsyncClient,
    async_db: AsyncSession,
) -> None:
    user_id = await _signup(async_client, "setup@example.com")

    resp = await async_client.post(
        "/api/v1/onboarding/catalog-setup",
        json={
            "symptoms": ["brain_fog", "pem"],
            "medications": ["ibuprofen"],
            "supplements": ["magnesium", "vitamin_d"],
            "trackers": ["Alcohol units", "Sick"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symptoms_created"] == 2
    assert body["medications_created"] == 1
    assert body["supplements_created"] == 2
    assert body["trackers_created"] == 2

    await _set_session_user_id(async_db, user_id)
    symptoms = (
        (
            await async_db.execute(
                select(SymptomCatalogItem.key).where(SymptomCatalogItem.archived.is_(False))
            )
        )
        .scalars()
        .all()
    )
    assert set(symptoms) == {"brain_fog", "pem"}

    trackers = (
        await async_db.execute(
            select(Tracker.name, Tracker.is_seed).where(Tracker.archived.is_(False))
        )
    ).all()
    assert ("Alcohol units", True) in trackers
    assert ("Sick", True) in trackers


async def test_catalog_setup_rejects_invalid_keys(async_client: AsyncClient) -> None:
    await _signup(async_client, "invalid-setup@example.com")

    resp = await async_client.post(
        "/api/v1/onboarding/catalog-setup",
        json={"symptoms": ["not_a_real_symptom"]},
    )
    assert resp.status_code == 400


async def test_catalog_setup_is_idempotent(
    async_client: AsyncClient, async_db: AsyncSession
) -> None:
    user_id = await _signup(async_client, "setup-idempotent@example.com")
    payload = {"supplements": ["nac"]}

    first = await async_client.post("/api/v1/onboarding/catalog-setup", json=payload)
    second = await async_client.post("/api/v1/onboarding/catalog-setup", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200

    await _set_session_user_id(async_db, user_id)
    count = (
        await async_db.execute(
            select(func.count())
            .select_from(SupplementCatalogItem)
            .where(SupplementCatalogItem.key == "nac")
        )
    ).scalar_one()
    assert count == 1
