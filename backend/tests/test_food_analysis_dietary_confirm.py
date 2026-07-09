"""HTTP-level tests for PUT /photos/{id}/analysis/dietary-confirm.

No app-code mocks: the route runs through the real service and commits to the
real (container) DB session.
"""

from __future__ import annotations

import datetime

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis

TEST_PIN = "1234"
_DATE = datetime.date(2026, 4, 1)


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


async def _make_photo_with_analysis(db: AsyncSession) -> int:
    entry = Entry(
        date=_DATE,
        schema_version=4,
        overall=2,
        bloating=0,
        stool_status="normal",
        joint_pain=0,
        neuro=0,
        sleep_quality=2,
        stress=1,
        diet_risk="normal",
        supplements="",
        sick=False,
        hot_shower=False,
        symptoms_json={},
    )
    db.add(entry)
    await db.flush()
    photo = Photo(entry_id=entry.id, filename="meal.jpg")
    db.add(photo)
    await db.flush()
    analysis = PhotoAnalysis(photo_id=photo.id, status="confirmed")
    db.add(analysis)
    await db.flush()
    await db.commit()
    return photo.id


async def test_dietary_confirm_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.put(
        "/api/v1/photos/1/analysis/dietary-confirm",
        json={"gluten_free_confirmed": True},
    )
    assert resp.status_code == 401


async def test_dietary_confirm_missing_analysis_404(authed_client: AsyncClient) -> None:
    resp = await authed_client.put(
        "/api/v1/photos/999999/analysis/dietary-confirm",
        json={"gluten_free_confirmed": True},
    )
    assert resp.status_code == 404


async def test_dietary_confirm_sets_and_returns_flags(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    photo_id = await _make_photo_with_analysis(async_db)

    resp = await authed_client.put(
        f"/api/v1/photos/{photo_id}/analysis/dietary-confirm",
        json={"gluten_free_confirmed": True, "lactose_free_confirmed": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["gluten_free_confirmed"] is True
    assert body["lactose_free_confirmed"] is True

    # Persisted: a follow-up GET reflects the new state.
    got = await authed_client.get(f"/api/v1/photos/{photo_id}/analysis")
    assert got.status_code == 200
    assert got.json()["gluten_free_confirmed"] is True
    assert got.json()["lactose_free_confirmed"] is True


async def test_dietary_confirm_partial_update_does_not_clobber_other_flag(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    photo_id = await _make_photo_with_analysis(async_db)

    # Set lactose-free first.
    await authed_client.put(
        f"/api/v1/photos/{photo_id}/analysis/dietary-confirm",
        json={"lactose_free_confirmed": True},
    )
    # Now set gluten-free only; lactose-free must remain True (not reset by omission).
    resp = await authed_client.put(
        f"/api/v1/photos/{photo_id}/analysis/dietary-confirm",
        json={"gluten_free_confirmed": True},
    )
    body = resp.json()
    assert body["gluten_free_confirmed"] is True
    assert body["lactose_free_confirmed"] is True
