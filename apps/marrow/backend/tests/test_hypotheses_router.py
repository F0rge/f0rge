"""HTTP-level tests for the hypothesis scoreboard (auth, CRUD, n-of-1, tenancy)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import signup_client

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_LEO_SEED_SQL = (_BACKEND_ROOT / "scripts" / "seed_leo_hypotheses.sql").read_text(encoding="utf-8")

_LIVE_L1 = {
    "slug": "l1-sibo-imo",
    "title": "L1 SIBO/IMO",
    "status": "live",
    "layer": 1,
    "kill_test": "negative prepped H2/CH4 + no high-folate/low-B12",
    "sort_order": 10,
}


async def test_list_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/hypotheses")
    assert resp.status_code == 401


async def test_update_unauthenticated_401(async_client: AsyncClient) -> None:
    resp = await async_client.put(
        "/api/v1/hypotheses/00000000-0000-0000-0000-000000000001",
        json={"status": "killed"},
    )
    assert resp.status_code == 401


async def test_list_empty_for_new_user(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/v1/hypotheses")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_list_update_round_trip(authed_client: AsyncClient) -> None:
    created = await authed_client.post("/api/v1/hypotheses", json=_LIVE_L1)
    assert created.status_code == 201
    body = created.json()
    assert body["slug"] == "l1-sibo-imo"
    assert body["status"] == "live"
    assert body["layer"] == 1
    hypothesis_id = body["id"]

    listed = await authed_client.get("/api/v1/hypotheses")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await authed_client.put(
        f"/api/v1/hypotheses/{hypothesis_id}",
        json={"status": "weakening", "last_evidence": "watching labs"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "weakening"
    assert updated.json()["last_evidence"] == "watching labs"
    assert updated.json()["kill_test"] == _LIVE_L1["kill_test"]

    fetched = await authed_client.get(f"/api/v1/hypotheses/{hypothesis_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "weakening"


async def test_killed_row_stays_on_list(authed_client: AsyncClient) -> None:
    created = await authed_client.post("/api/v1/hypotheses", json=_LIVE_L1)
    hypothesis_id = created.json()["id"]
    killed = await authed_client.put(
        f"/api/v1/hypotheses/{hypothesis_id}",
        json={"status": "killed"},
    )
    assert killed.status_code == 200
    assert killed.json()["status"] == "killed"

    all_rows = await authed_client.get("/api/v1/hypotheses")
    assert [row["id"] for row in all_rows.json()] == [hypothesis_id]

    live_only = await authed_client.get("/api/v1/hypotheses", params={"status": "live"})
    assert live_only.json() == []

    delete_resp = await authed_client.delete(f"/api/v1/hypotheses/{hypothesis_id}")
    assert delete_resp.status_code == 405


async def test_duplicate_slug_409(authed_client: AsyncClient) -> None:
    first = await authed_client.post("/api/v1/hypotheses", json=_LIVE_L1)
    assert first.status_code == 201
    second = await authed_client.post("/api/v1/hypotheses", json=_LIVE_L1)
    assert second.status_code == 409


async def test_invalid_status_and_layer_422(authed_client: AsyncClient) -> None:
    bad_status = await authed_client.post(
        "/api/v1/hypotheses",
        json={**_LIVE_L1, "status": "confirmed"},
    )
    assert bad_status.status_code == 422

    bad_layer = await authed_client.post(
        "/api/v1/hypotheses",
        json={**_LIVE_L1, "slug": "l3-ileum-celiac", "layer": 3},
    )
    assert bad_layer.status_code == 422

    bad_filter = await authed_client.get("/api/v1/hypotheses", params={"status": "done"})
    assert bad_filter.status_code == 422


async def test_n_of_1_upsert_one_slot(authed_client: AsyncClient) -> None:
    empty = await authed_client.get("/api/v1/hypotheses/n-of-1")
    assert empty.status_code == 200
    assert empty.json() is None

    payload = {
        "change": "pause evening ibuprofen",
        "start": "2026-08-01",
        "watch_field": "bloating",
        "stop_rule": "14 days or flare week with flat CRP",
    }
    created = await authed_client.put("/api/v1/hypotheses/n-of-1", json=payload)
    assert created.status_code == 200
    first_id = created.json()["id"]

    updated = await authed_client.put(
        "/api/v1/hypotheses/n-of-1",
        json={**payload, "change": "continue pause"},
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == first_id
    assert updated.json()["change"] == "continue pause"

    fetched = await authed_client.get("/api/v1/hypotheses/n-of-1")
    assert fetched.json()["id"] == first_id


async def test_tenant_isolation(
    async_db: AsyncSession,
) -> None:
    alice = await signup_client(async_db, "alice-hyp@example.com", handle="alice_h")
    bob = await signup_client(async_db, "bob-hyp@example.com", handle="bob_h")
    try:
        created = await alice.post("/api/v1/hypotheses", json=_LIVE_L1)
        assert created.status_code == 201
        hypothesis_id = created.json()["id"]

        bob_list = await bob.get("/api/v1/hypotheses")
        assert bob_list.json() == []

        bob_get = await bob.get(f"/api/v1/hypotheses/{hypothesis_id}")
        assert bob_get.status_code == 404

        bob_put = await bob.put(
            f"/api/v1/hypotheses/{hypothesis_id}",
            json={"status": "killed"},
        )
        assert bob_put.status_code == 404

        alice_list = await alice.get("/api/v1/hypotheses")
        assert len(alice_list.json()) == 1
    finally:
        await alice.aclose()
        await bob.aclose()


async def test_leo_seed_sql_full_board(async_db: AsyncSession) -> None:
    client = await signup_client(async_db, "leo.board@example.com", handle="leo")
    try:
        await async_db.execute(text(_LEO_SEED_SQL))
        await async_db.flush()
        listed = await client.get("/api/v1/hypotheses")
        assert listed.status_code == 200
        rows = listed.json()
        assert [row["slug"] for row in rows] == [
            "l1-sibo-imo",
            "l2-gastric-b12",
            "l3-ileum-celiac",
            "l4-flare-ibuprofen",
            "l5-hpg-quiet",
            "k1-structural-heart",
            "k2-structural-neuro",
            "p1-tcd-lamotrigine",
            "p2-hla-dq",
        ]
        assert rows[0]["layer"] == 1
        assert rows[1]["layer"] == 2
        assert rows[2]["layer"] is None
        assert rows[2]["last_evidence"] == "scopes still only ordered; GFD 8 months"
        assert rows[5]["cite"] == "CUF Mar 2026"
    finally:
        await client.aclose()
