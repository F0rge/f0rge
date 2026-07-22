from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_checkin_defaults_roundtrip(authed_client: AsyncClient) -> None:
    initial = await authed_client.get("/api/v1/settings")
    assert initial.status_code == 200
    assert initial.json()["default_supplements"] == []
    assert initial.json()["default_symptoms"] == {}

    payload = {
        "default_supplements": ["magnesium", "vitamin_d"],
        "default_symptoms": {"bloating": 3, "fatigue": 5},
    }
    put_resp = await authed_client.put("/api/v1/settings/checkin-defaults", json=payload)
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["default_supplements"] == ["magnesium", "vitamin_d"]
    assert body["default_symptoms"] == {"bloating": 3, "fatigue": 5}

    get_resp = await authed_client.get("/api/v1/settings")
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["default_supplements"] == ["magnesium", "vitamin_d"]
    assert fetched["default_symptoms"] == {"bloating": 3, "fatigue": 5}


@pytest.mark.asyncio
async def test_checkin_defaults_empty_payload_clears(authed_client: AsyncClient) -> None:
    await authed_client.put(
        "/api/v1/settings/checkin-defaults",
        json={
            "default_supplements": ["magnesium"],
            "default_symptoms": {"bloating": 2},
        },
    )

    clear_resp = await authed_client.put(
        "/api/v1/settings/checkin-defaults",
        json={"default_supplements": [], "default_symptoms": {}},
    )
    assert clear_resp.status_code == 200
    body = clear_resp.json()
    assert body["default_supplements"] == []
    assert body["default_symptoms"] == {}

    get_resp = await authed_client.get("/api/v1/settings")
    assert get_resp.json()["default_supplements"] == []
    assert get_resp.json()["default_symptoms"] == {}


@pytest.mark.asyncio
async def test_checkin_defaults_invalid_severity_422(authed_client: AsyncClient) -> None:
    resp = await authed_client.put(
        "/api/v1/settings/checkin-defaults",
        json={"default_supplements": [], "default_symptoms": {"bloating": 11}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_checkin_defaults_invalid_key_422(authed_client: AsyncClient) -> None:
    resp = await authed_client.put(
        "/api/v1/settings/checkin-defaults",
        json={"default_supplements": ["Bad-Key"], "default_symptoms": {}},
    )
    assert resp.status_code == 422
