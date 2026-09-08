"""HTTP tests for timed symptom events on entries."""

from __future__ import annotations

from httpx import AsyncClient

_VALID_PAYLOAD = {
    "date": "2026-02-01",
    "overall": 3,
    "bloating": 1,
    "stool_status": "normal",
    "joint_pain": 0,
    "neuro": 0,
    "sleep_quality": 4,
    "stress": 2,
    "diet_risk": "",
    "supplements": "",
    "sick": False,
}


async def test_create_entry_with_symptom_events_round_trips(
    authed_client: AsyncClient,
) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["symptoms_json"] = {"vss": 7}
    payload["symptom_events"] = [
        {"key": "vss", "severity": 7, "time": "15:20"},
        {"key": "vss", "severity": 4},
    ]

    create_resp = await authed_client.post("/api/v1/entries", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["symptoms_json"] == {"vss": 7}
    assert created["symptom_events"] == [
        {"key": "vss", "severity": 7, "time": "15:20"},
        {"key": "vss", "severity": 4, "time": None},
    ]

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.status_code == 200
    assert get_resp.json()["symptom_events"] == created["symptom_events"]


async def test_create_entry_omits_symptom_events_defaults_to_empty_list(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["symptom_events"] == []


async def test_update_entry_sets_symptom_events(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    update_resp = await authed_client.put(
        "/api/v1/entries/2026-02-01",
        json={
            "symptoms_json": {"tinnitus": 6},
            "symptom_events": [{"key": "tinnitus", "severity": 6, "time": "09:05"}],
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["symptom_events"] == [
        {"key": "tinnitus", "severity": 6, "time": "09:05"}
    ]


async def test_update_entry_omitting_symptom_events_leaves_them_unchanged(
    authed_client: AsyncClient,
) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["symptom_events"] = [{"key": "vss", "severity": 5, "time": "08:00"}]
    await authed_client.post("/api/v1/entries", json=payload)

    update_resp = await authed_client.put("/api/v1/entries/2026-02-01", json={"overall": 1})
    assert update_resp.status_code == 200
    assert update_resp.json()["symptom_events"] == [{"key": "vss", "severity": 5, "time": "08:00"}]


async def test_symptom_event_rejects_bad_key_and_severity(
    authed_client: AsyncClient,
) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["symptom_events"] = [{"key": "VSS", "severity": 7, "time": "10:00"}]
    bad_key = await authed_client.post("/api/v1/entries", json=payload)
    assert bad_key.status_code == 422

    payload["date"] = "2026-02-02"
    payload["symptom_events"] = [{"key": "vss", "severity": 11, "time": "10:00"}]
    bad_sev = await authed_client.post("/api/v1/entries", json=payload)
    assert bad_sev.status_code == 422
