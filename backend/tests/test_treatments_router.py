"""HTTP-level tests for discontinuing a treatment (end_reason/end_note on the
existing PUT /treatments/{id}). No mocks of app code -- exercises the real
create/update service path, per feedback_no_mocks_at_seam_under_test.md.
"""

from __future__ import annotations

import bcrypt
import pytest
from httpx import AsyncClient

from app.config import settings

TEST_PIN = "1234"

_VALID_PAYLOAD = {
    "name": "Rifaximin",
    "type": "antibiotic",
    "start_date": "2026-01-01",
}


@pytest.fixture(autouse=True)
def known_pin(monkeypatch: pytest.MonkeyPatch) -> str:
    hashed = bcrypt.hashpw(TEST_PIN.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    monkeypatch.setattr(settings, "pin_hash", hashed)
    return TEST_PIN


@pytest.fixture
async def authed_client(async_client: AsyncClient) -> AsyncClient:
    """The house async_client, logged in via a real login round-trip."""
    resp = await async_client.post("/api/v1/auth/login", json={"pin": TEST_PIN})
    assert resp.status_code == 200
    return async_client


async def test_create_persists_end_reason_and_note(authed_client: AsyncClient) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["end_date"] = "2026-01-14"
    payload["end_reason"] = "side_effects"
    payload["end_note"] = "Nausea after day 10"

    resp = await authed_client.post("/api/v1/treatments", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["end_reason"] == "side_effects"
    assert body["end_note"] == "Nausea after day 10"


async def test_create_invalid_end_reason_422(authed_client: AsyncClient) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["end_reason"] = "not_a_real_reason"

    resp = await authed_client.post("/api/v1/treatments", json=payload)
    assert resp.status_code == 422


async def test_discontinue_via_put_round_trips(authed_client: AsyncClient) -> None:
    """The primary path: frontend "discontinues" via PUT with end_date + reason."""
    create_resp = await authed_client.post("/api/v1/treatments", json=_VALID_PAYLOAD)
    assert create_resp.status_code == 201
    treatment_id = create_resp.json()["id"]

    put_resp = await authed_client.put(
        f"/api/v1/treatments/{treatment_id}",
        json={
            "end_date": "2026-01-20",
            "end_reason": "ineffective",
            "end_note": "No improvement after 3 weeks",
        },
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["end_date"] == "2026-01-20"
    assert body["end_reason"] == "ineffective"
    assert body["end_note"] == "No improvement after 3 weeks"

    get_resp = await authed_client.get(f"/api/v1/treatments/{treatment_id}")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["end_reason"] == "ineffective"
    assert fetched["end_note"] == "No improvement after 3 weeks"


async def test_update_invalid_end_reason_422(authed_client: AsyncClient) -> None:
    create_resp = await authed_client.post("/api/v1/treatments", json=_VALID_PAYLOAD)
    treatment_id = create_resp.json()["id"]

    resp = await authed_client.put(
        f"/api/v1/treatments/{treatment_id}",
        json={"end_reason": "not_a_real_reason"},
    )
    assert resp.status_code == 422


async def test_update_without_end_reason_stays_null(authed_client: AsyncClient) -> None:
    """Legacy end_date-only discontinuation (no reason given) still works."""
    create_resp = await authed_client.post("/api/v1/treatments", json=_VALID_PAYLOAD)
    treatment_id = create_resp.json()["id"]

    resp = await authed_client.put(
        f"/api/v1/treatments/{treatment_id}",
        json={"end_date": "2026-01-20"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["end_date"] == "2026-01-20"
    assert body["end_reason"] is None
