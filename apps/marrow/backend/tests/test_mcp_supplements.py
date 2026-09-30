"""MCP supplement tools, exercised end to end through the tool functions.

These use the *real* ``scoped_*_session`` open/close semantics (committed rows,
``real_scoped_sessions``) rather than a mocked savepoint session, so a payload built
from detached/expired ORM rows (PR #791's DetachedInstanceError) fails here.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.models.entry import Entry
from app.models.supplement_catalog import SupplementCatalogItem
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH
from f0rge_core.exceptions import ValidationError
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session

# real_scoped_sessions / _mcp_tool are shared with the PR #791 regression tests.
from tests.test_mcp_database import _mcp_tool, committed_day, real_scoped_sessions  # noqa: F401

USER_A = uuid.UUID(settings.default_storage_user_id)
DAY = datetime.date(2031, 6, 10)
# Catalog keys are namespaced so they never collide with the seeded default catalog.
ACTIVE_KEYS = ["tsupp_nac", "tsupp_mag", "tsupp_zinc"]
ARCHIVED_KEY = "tsupp_old"


class _Ctx:
    def __init__(self, user_id: uuid.UUID) -> None:
        self.client_id = str(user_id)


async def _seed_catalog(engine, user_id: uuid.UUID, keys: list[str], archived: list[str]) -> None:
    async with engine.begin() as conn:
        for i, key in enumerate(keys + archived):
            await conn.execute(
                sa.text(
                    "INSERT INTO supplement_catalog "
                    "(user_id, key, label, archived, sort_order, created_at, updated_at) "
                    "VALUES (:u, :k, :l, :a, :s, now(), now())"
                ),
                {
                    "u": user_id,
                    "k": key,
                    "l": key.upper(),
                    "a": key in archived,
                    "s": 900 + i,
                },
            )


async def _cleanup(engine, user_ids: list[uuid.UUID]) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM entries WHERE user_id = ANY(:u) AND date = ANY(:d)"),
            {"u": user_ids, "d": [DAY, DAY + datetime.timedelta(days=1)]},
        )
        await conn.execute(
            sa.text("DELETE FROM supplement_catalog WHERE key LIKE 'tsupp\\_%'"),
        )


@pytest_asyncio.fixture
async def supp_world(superuser_engine, real_scoped_sessions) -> AsyncIterator[uuid.UUID]:  # noqa: F811
    """User A (default user) + user B, each with their own committed catalogs.

    A: tsupp_nac / tsupp_mag / tsupp_zinc active, tsupp_old archived.
    B: tsupp_b_only active, plus tsupp_nac (same key, B's own row).
    Yields user B's id.
    """
    user_b = uuid.uuid4()
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, avatar_default_index, created_at) "
                "VALUES (:id, :e, :p, 0, now())"
            ),
            {"id": user_b, "e": f"supp-b-{user_b}@example.com", "p": LEO_PLACEHOLDER_PASSWORD_HASH},
        )
    await _seed_catalog(superuser_engine, USER_A, ACTIVE_KEYS, [ARCHIVED_KEY])
    await _seed_catalog(superuser_engine, user_b, ["tsupp_b_only", "tsupp_nac"], [])
    try:
        yield user_b
    finally:
        await _cleanup(superuser_engine, [USER_A, user_b])
        async with superuser_engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": user_b})


async def _row(async_engine, user_id: uuid.UUID, day: datetime.date) -> Any:
    """Read the raw entry row as ``user_id`` through RLS (None if absent)."""
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    async with maker() as s:
        await apply_session_user_id(s, user_id)
        row = (
            await s.execute(
                sa.select(Entry.supplements, Entry.updated_at, Entry.entry_time).where(
                    Entry.user_id == user_id, Entry.date == day
                )
            )
        ).one_or_none()
        await s.rollback()
        await clear_tenant_session(s)
        return row


async def _catalog_row(async_engine, user_id: uuid.UUID, key: str) -> Any:
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    async with maker() as s:
        await apply_session_user_id(s, user_id)
        row = (
            await s.execute(
                sa.select(
                    SupplementCatalogItem.first_used_at, SupplementCatalogItem.last_used_at
                ).where(SupplementCatalogItem.user_id == user_id, SupplementCatalogItem.key == key)
            )
        ).one_or_none()
        await s.rollback()
        await clear_tenant_session(s)
        return row


async def _set(keys, date=DAY, mode="replace", user=USER_A):
    return await _mcp_tool("set_supplements")(
        keys=keys, date=str(date) if date else None, mode=mode, ctx=_Ctx(user)
    )


# ---------------------------------------------------------------------------
# list_supplements
# ---------------------------------------------------------------------------


async def test_list_supplements_active_only_then_with_archived(supp_world) -> None:
    result = await _mcp_tool("list_supplements")(ctx=_Ctx(USER_A))
    keys = [s["key"] for s in result["supplements"] if s["key"].startswith("tsupp_")]
    assert keys == ACTIVE_KEYS
    first = next(s for s in result["supplements"] if s["key"] == "tsupp_nac")
    assert set(first) == {
        "id",
        "key",
        "label",
        "archived",
        "sort_order",
        "first_used_at",
        "last_used_at",
    }
    assert first["archived"] is False and first["label"] == "TSUPP_NAC"

    with_archived = await _mcp_tool("list_supplements")(include_archived=True, ctx=_Ctx(USER_A))
    by_key = {s["key"]: s for s in with_archived["supplements"]}
    assert by_key[ARCHIVED_KEY]["archived"] is True


async def test_list_supplements_tenant_isolation(supp_world) -> None:
    user_b = supp_world
    result_b = await _mcp_tool("list_supplements")(include_archived=True, ctx=_Ctx(user_b))
    keys_b = {s["key"] for s in result_b["supplements"] if s["key"].startswith("tsupp_")}
    assert keys_b == {"tsupp_b_only", "tsupp_nac"}
    result_a = await _mcp_tool("list_supplements")(include_archived=True, ctx=_Ctx(USER_A))
    keys_a = {s["key"] for s in result_a["supplements"]}
    assert "tsupp_b_only" not in keys_a
    # Same key, different per-user row id.
    id_a = next(s["id"] for s in result_a["supplements"] if s["key"] == "tsupp_nac")
    id_b = next(s["id"] for s in result_b["supplements"] if s["key"] == "tsupp_nac")
    assert id_a != id_b


# ---------------------------------------------------------------------------
# set_supplements
# ---------------------------------------------------------------------------


async def test_replace_creates_day_and_touches_catalog(supp_world, async_engine) -> None:
    assert await _row(async_engine, USER_A, DAY) is None
    assert (await _catalog_row(async_engine, USER_A, "tsupp_nac")).first_used_at is None

    result = await _set(["TSUPP_NAC", "tsupp-mag", "tsupp_nac"])  # normalised + de-duplicated

    assert result == {
        "date": str(DAY),
        "mode": "replace",
        "previous_supplements": [],
        "supplements": ["tsupp_nac", "tsupp_mag"],
        "added": ["tsupp_nac", "tsupp_mag"],
        "removed": [],
        "changed": True,
        "created_day": True,
    }
    assert (await _row(async_engine, USER_A, DAY)).supplements == "tsupp_nac,tsupp_mag"
    touched = await _catalog_row(async_engine, USER_A, "tsupp_nac")
    assert touched.first_used_at is not None and touched.last_used_at is not None
    assert (await _catalog_row(async_engine, USER_A, "tsupp_zinc")).first_used_at is None


async def test_replace_add_remove_sequence(supp_world, async_engine) -> None:
    await _set(["tsupp_nac"])
    added = await _set(["tsupp_zinc", "tsupp_nac"], mode="add")
    assert added["previous_supplements"] == ["tsupp_nac"]
    assert added["supplements"] == ["tsupp_nac", "tsupp_zinc"]  # existing order kept
    assert added["added"] == ["tsupp_zinc"] and added["removed"] == []
    assert added["changed"] is True and added["created_day"] is False

    removed = await _set(["tsupp_nac", "tsupp_mag"], mode="remove")  # mag not present: fine
    assert removed["supplements"] == ["tsupp_zinc"]
    assert removed["removed"] == ["tsupp_nac"]

    replaced = await _set(["tsupp_mag"], mode="replace")
    assert replaced["supplements"] == ["tsupp_mag"]
    assert replaced["added"] == ["tsupp_mag"] and replaced["removed"] == ["tsupp_zinc"]

    cleared = await _set([], mode="replace")
    assert cleared["supplements"] == [] and cleared["changed"] is True
    assert (await _row(async_engine, USER_A, DAY)).supplements == ""


async def test_noop_does_not_write(supp_world, async_engine) -> None:
    await _set(["tsupp_nac", "tsupp_mag"])
    before = await _row(async_engine, USER_A, DAY)

    same_replace = await _set(["tsupp_mag", "tsupp_nac"][::-1])  # same order as stored
    add_existing = await _set(["tsupp_nac"], mode="add")
    remove_missing = await _set(["tsupp_zinc"], mode="remove")
    for res in (same_replace, add_existing, remove_missing):
        assert res["changed"] is False
        assert res["added"] == [] and res["removed"] == []
        assert res["supplements"] == ["tsupp_nac", "tsupp_mag"]

    after = await _row(async_engine, USER_A, DAY)
    assert after.updated_at == before.updated_at
    assert after.entry_time == before.entry_time


async def test_noop_on_missing_day_does_not_create_row(supp_world, async_engine) -> None:
    res = await _set([], mode="replace")
    assert res["changed"] is False and res["created_day"] is False
    assert await _row(async_engine, USER_A, DAY) is None
    res = await _set(["tsupp_nac"], mode="remove")
    assert res["changed"] is False
    assert await _row(async_engine, USER_A, DAY) is None


async def test_unknown_key_rejected_with_valid_keys_listed(supp_world, async_engine) -> None:
    with pytest.raises(ValidationError) as exc:
        await _set(["tsupp_nac", "nope_not_real"])
    msg = exc.value.detail
    assert "nope_not_real" in msg
    for valid in ACTIVE_KEYS:
        assert valid in msg
    assert ARCHIVED_KEY not in msg  # archived keys are not advertised as valid
    assert await _row(async_engine, USER_A, DAY) is None  # nothing written


async def test_unknown_key_rejected_for_remove_too(supp_world) -> None:
    with pytest.raises(ValidationError):
        await _set(["nope_not_real"], mode="remove")


async def test_empty_or_garbage_key_rejected(supp_world) -> None:
    with pytest.raises(ValidationError):
        await _set(["  !!  "])


async def test_archived_key_cannot_be_added_but_can_be_removed(
    supp_world, superuser_engine, async_engine
) -> None:
    for mode in ("add", "replace"):
        with pytest.raises(ValidationError, match=ARCHIVED_KEY):
            await _set([ARCHIVED_KEY], mode=mode)
    assert await _row(async_engine, USER_A, DAY) is None

    # A key archived *after* being logged stays on the day and is removable.
    await _set(["tsupp_nac", "tsupp_zinc"])
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text("UPDATE supplement_catalog SET archived = true WHERE key = 'tsupp_zinc'")
        )
    kept = await _set(["tsupp_zinc", "tsupp_nac"], mode="replace")  # historical, unchanged
    assert kept["changed"] is False
    removed = await _set(["tsupp_zinc"], mode="remove")
    assert removed["supplements"] == ["tsupp_nac"]


async def test_invalid_inputs(supp_world) -> None:
    with pytest.raises(ValueError):
        await _set(["tsupp_nac"], date="not-a-date")
    with pytest.raises(ValidationError, match="mode"):
        await _set(["tsupp_nac"], mode="toggle")


async def test_default_date_is_local_today(supp_world, async_engine) -> None:
    with patch("app.mcp.tools.supplements.local_today", return_value=DAY):
        result = await _mcp_tool("set_supplements")(keys=["tsupp_mag"], ctx=_Ctx(USER_A))
    assert result["date"] == str(DAY)
    assert (await _row(async_engine, USER_A, DAY)).supplements == "tsupp_mag"


async def test_only_target_day_touched(supp_world, async_engine) -> None:
    other = DAY + datetime.timedelta(days=1)
    await _set(["tsupp_nac"], date=other)
    await _set(["tsupp_mag"])
    assert (await _row(async_engine, USER_A, other)).supplements == "tsupp_nac"
    assert (await _row(async_engine, USER_A, DAY)).supplements == "tsupp_mag"


# ---------------------------------------------------------------------------
# get_day / list_days
# ---------------------------------------------------------------------------


async def test_get_day_and_list_days_include_supplements(supp_world) -> None:
    await _set(["tsupp_nac", "tsupp_zinc"])
    day = await _mcp_tool("get_day")(date=str(DAY), ctx=_Ctx(USER_A))
    assert day["supplements"] == ["tsupp_nac", "tsupp_zinc"]
    listed = await _mcp_tool("list_days")(start_date=str(DAY), end_date=str(DAY), ctx=_Ctx(USER_A))
    assert listed["days"][0]["supplements"] == ["tsupp_nac", "tsupp_zinc"]

    await _set([], mode="replace")
    day = await _mcp_tool("get_day")(date=str(DAY), ctx=_Ctx(USER_A))
    assert day["supplements"] == []


async def test_committed_day_fixture_reports_empty_supplements(
    committed_day,  # noqa: F811
    real_scoped_sessions,  # noqa: F811
) -> None:
    day = await _mcp_tool("get_day")(date=str(committed_day), ctx=_Ctx(USER_A))
    assert day["supplements"] == []
    listed = await _mcp_tool("list_days")(
        start_date=str(committed_day), end_date=str(committed_day), ctx=_Ctx(USER_A)
    )
    assert listed["days"][0]["supplements"] == []


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


async def test_user_b_cannot_see_or_modify_user_a(supp_world, async_engine) -> None:
    user_b = supp_world
    await _set(["tsupp_nac", "tsupp_mag"])  # user A's day

    # B can't read A's day through get_day / list_days.
    assert await _mcp_tool("get_day")(date=str(DAY), ctx=_Ctx(user_b)) is None
    listed = await _mcp_tool("list_days")(start_date=str(DAY), end_date=str(DAY), ctx=_Ctx(user_b))
    assert listed["days"] == []

    # A's keys that B doesn't have in B's catalog are unknown to B.
    with pytest.raises(ValidationError, match="tsupp_mag"):
        await _set(["tsupp_mag"], user=user_b)

    # B writes the same date: creates B's own row, A's row is untouched.
    res = await _set(["tsupp_nac", "tsupp_b_only"], user=user_b)
    assert res["created_day"] is True and res["previous_supplements"] == []
    assert (await _row(async_engine, user_b, DAY)).supplements == "tsupp_nac,tsupp_b_only"
    assert (await _row(async_engine, USER_A, DAY)).supplements == "tsupp_nac,tsupp_mag"

    # Catalog first_used_at: B touching tsupp_nac must not touch A's catalog row, and vice versa.
    assert (await _catalog_row(async_engine, user_b, "tsupp_b_only")).first_used_at is not None
    assert (await _catalog_row(async_engine, USER_A, "tsupp_zinc")).first_used_at is None
