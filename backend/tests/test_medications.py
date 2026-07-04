"""HTTP-level tests for the Medications feature: catalog router + the
`medications` field on entries.

No mocks of app code -- create_entry/update_entry call through to the real
obsidian vault writer, which no-ops safely when settings.vault_path is
unwritable/unset, per feedback_no_mocks_at_seam_under_test.md.
"""

from __future__ import annotations

import datetime

import bcrypt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.entry import Entry
from app.services import medication_catalog as medication_catalog_service

TEST_PIN = "1234"

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


# ---------------------------------------------------------------------------
# Vault render -- archived key still resolves to its label, not the raw key
# ---------------------------------------------------------------------------


async def test_render_markdown_resolves_archived_medication_label(
    async_db: AsyncSession,
) -> None:
    from app.services.obsidian import _render_markdown

    item = await medication_catalog_service.create_item(async_db, "imodium", "Imodium")
    await medication_catalog_service.update_item(async_db, "imodium", {"archived": True})

    entry = Entry(
        date=datetime.date(2026, 5, 15),
        schema_version=3,
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
        medications_json=[{"key": "imodium", "reason": "upset stomach"}],
    )
    async_db.add(entry)
    await async_db.commit()
    await async_db.refresh(entry)

    content = _render_markdown(
        entry=entry,
        photos=[],
        analyses={},
        active_sym_labels={},
        active_treatments=[],
        health=None,
        weather=None,
        med_labels={item.key: item.label},
    )
    assert "Imodium (for upset stomach)" in content
    assert "## Medications" in content
