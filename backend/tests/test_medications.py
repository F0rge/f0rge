"""HTTP-level tests for the Medications feature: catalog router + the
`medications` field on entries.

No mocks of app code.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import medication_catalog as medication_catalog_service

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


# ---------------------------------------------------------------------------
# GET /api/v1/medications/catalog
# ---------------------------------------------------------------------------


async def test_get_catalog_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/medications/catalog")
    assert resp.status_code == 401


async def test_get_catalog_returns_seeded_meds(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    """The migration seeds these rows on a real deploy; testcontainers uses
    create_all (not the alembic chain), so seed them here to prove the
    endpoint shape against the same rows the migration would produce."""
    await medication_catalog_service.create_item(async_db, "ibuprofen", "Ibuprofen")
    await medication_catalog_service.create_item(async_db, "paracetamol", "Paracetamol")

    resp = await authed_client.get("/api/v1/medications/catalog")
    assert resp.status_code == 200
    body = resp.json()
    keys = {item["key"] for item in body}
    assert keys == {"ibuprofen", "paracetamol"}
    item = next(i for i in body if i["key"] == "ibuprofen")
    assert item["label"] == "Ibuprofen"
    assert item["archived"] is False


async def test_post_catalog_item_creates_and_returns_201(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        "/api/v1/medications/catalog", json={"key": "aspirin", "label": "Aspirin"}
    )
    assert resp.status_code == 201
    assert resp.json()["key"] == "aspirin"


async def test_patch_catalog_item_archives(authed_client: AsyncClient) -> None:
    await authed_client.post(
        "/api/v1/medications/catalog", json={"key": "aspirin", "label": "Aspirin"}
    )
    resp = await authed_client.patch("/api/v1/medications/catalog/aspirin", json={"archived": True})
    assert resp.status_code == 200
    assert resp.json()["archived"] is True


# ---------------------------------------------------------------------------
# `medications` field on entries -- round-trips through EntryCreate/EntryResponse
# ---------------------------------------------------------------------------


async def test_create_entry_with_medications_round_trips(authed_client: AsyncClient) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["medications"] = [
        {"key": "ibuprofen", "dose": "400mg", "reason": "headache", "time": "15:20"},
        {"key": "paracetamol"},  # dose/reason/time all optional
    ]

    create_resp = await authed_client.post("/api/v1/entries", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["medications"] == [
        {"key": "ibuprofen", "dose": "400mg", "reason": "headache", "time": "15:20"},
        {"key": "paracetamol", "dose": None, "reason": None, "time": None},
    ]

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.status_code == 200
    assert get_resp.json()["medications"] == created["medications"]


async def test_create_entry_omits_medications_defaults_to_empty_list(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)
    assert resp.status_code == 201
    assert resp.json()["medications"] == []


async def test_update_entry_sets_medications(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/v1/entries", json=_VALID_PAYLOAD)

    update_resp = await authed_client.put(
        "/api/v1/entries/2026-02-01",
        json={"medications": [{"key": "ibuprofen", "dose": "200mg"}]},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["medications"] == [
        {"key": "ibuprofen", "dose": "200mg", "reason": None, "time": None}
    ]

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.json()["medications"] == [
        {"key": "ibuprofen", "dose": "200mg", "reason": None, "time": None}
    ]


async def test_update_entry_omitting_medications_leaves_them_unchanged(
    authed_client: AsyncClient,
) -> None:
    payload = dict(_VALID_PAYLOAD)
    payload["medications"] = [{"key": "ibuprofen", "dose": "400mg"}]
    await authed_client.post("/api/v1/entries", json=payload)

    # Partial update that does not mention `medications` at all.
    update_resp = await authed_client.put("/api/v1/entries/2026-02-01", json={"overall": 1})
    assert update_resp.status_code == 200
    assert update_resp.json()["medications"] == [
        {"key": "ibuprofen", "dose": "400mg", "reason": None, "time": None}
    ]


async def test_archived_catalog_key_preserved_on_historical_entry(
    authed_client: AsyncClient, async_db: AsyncSession
) -> None:
    """A medication logged on a past entry must still show up in the
    entry's `medications` list even after the catalog item is archived --
    the key is not FK-constrained and archiving must not strip history."""
    await medication_catalog_service.create_item(async_db, "imodium", "Imodium")

    payload = dict(_VALID_PAYLOAD)
    payload["medications"] = [{"key": "imodium", "reason": "upset stomach"}]
    create_resp = await authed_client.post("/api/v1/entries", json=payload)
    assert create_resp.status_code == 201

    await medication_catalog_service.update_item(async_db, "imodium", {"archived": True})

    get_resp = await authed_client.get("/api/v1/entries/2026-02-01")
    assert get_resp.status_code == 200
    assert get_resp.json()["medications"] == [
        {"key": "imodium", "dose": None, "reason": "upset stomach", "time": None}
    ]
