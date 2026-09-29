from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.mcp.database import scoped_main_session
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session


@pytest.mark.asyncio
async def test_rollback_before_clear_tenant_after_failed_sql(async_db: AsyncSession) -> None:
    """Regression: aborted transactions must not make RESET raise InFailedSQLTransactionError."""
    uid = uuid.UUID(settings.default_storage_user_id)
    await apply_session_user_id(async_db, uid)
    with pytest.raises(sa.exc.ProgrammingError):
        await async_db.execute(sa.text("SELECT * FROM no_such_mcp_cleanup_table"))
    await async_db.rollback()
    await clear_tenant_session(async_db)


@pytest.mark.asyncio
async def test_scoped_main_session_cleanup_after_failed_sql(async_engine) -> None:
    """MCP scoped_main_session rolls back before RESET (matches FastAPI get_db)."""
    uid = uuid.UUID(settings.default_storage_user_id)
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    with patch("app.mcp.database.make_main_session", side_effect=lambda: maker()):
        with pytest.raises(sa.exc.ProgrammingError):
            async with scoped_main_session(uid) as db:
                await db.execute(sa.text("SELECT * FROM no_such_mcp_cleanup_table_xyz"))


# ---------------------------------------------------------------------------
# Regression: MCP read tools build payloads from ORM rows *after* the scoped
# session closes. Cleanup must not expire those rows (DetachedInstanceError:
# "Instance <Entry> is not bound to a Session; attribute refresh operation
# cannot proceed") — see get_day / list_days / treatments in prod on 2026-09-29.
# ---------------------------------------------------------------------------


def _mcp_tool(name: str):
    from mcp.server.fastmcp import FastMCP

    from app.mcp import tools as t_mod

    server = FastMCP("test")
    t_mod.register_tools(server)
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


@pytest.fixture
async def committed_day(superuser_engine, async_engine):
    """Committed Entry + Photo + Treatment + dose log for the default user.

    Uses real (non-savepoint) commits so ``scoped_ro_session`` — which opens its
    own connection — can see the rows, then removes them.
    """
    import datetime

    from app.models.entry import Entry
    from app.models.photo import Photo
    from app.models.treatment import Treatment
    from app.models.treatment_log import TreatmentLog

    uid = uuid.UUID(settings.default_storage_user_id)
    day = datetime.date(2031, 3, 4)
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    async with maker() as s:
        await apply_session_user_id(s, uid)
        entry = Entry(
            date=day,
            overall=7,
            bloating=3,
            joint_pain=1,
            neuro=1,
            diet_risk="",
            supplements="",
            sick=False,
            hot_shower=False,
            notes="regression day",
        )
        s.add(entry)
        await s.flush()
        photo = Photo(user_id=uid, entry_id=entry.id, filename=None, label="Oats", meal_time=None)
        treatment = Treatment(
            name="Regression-Tx",
            normalized_name="regression-tx",
            type="supplement",
            start_date=day - datetime.timedelta(days=5),
            end_date=None,
            dose="1x",
        )
        s.add_all([photo, treatment])
        await s.flush()
        s.add(TreatmentLog(treatment_id=treatment.id, date=day, doses_taken=1))
        await s.commit()
        ids = (entry.id, treatment.id)
        await clear_tenant_session(s)
    try:
        yield day
    finally:
        async with superuser_engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM treatment_log WHERE treatment_id=:t"), {"t": ids[1]}
            )
            await conn.execute(sa.text("DELETE FROM treatments WHERE id=:t"), {"t": ids[1]})
            await conn.execute(sa.text("DELETE FROM photos WHERE entry_id=:e"), {"e": ids[0]})
            await conn.execute(sa.text("DELETE FROM entries WHERE id=:e"), {"e": ids[0]})


@pytest.fixture
def real_scoped_sessions(async_engine):
    """Route MCP scoped sessions to the test_app engine but keep real open/close semantics."""
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    with (
        patch("app.mcp.database.make_ro_session", side_effect=lambda: maker()),
        patch("app.mcp.database.make_main_session", side_effect=lambda: maker()),
    ):
        yield


@pytest.mark.asyncio
async def test_get_day_end_to_end_after_session_close(committed_day, real_scoped_sessions) -> None:
    from f0rge_db.auth_context import user_id_ctx

    tok = user_id_ctx.set(uuid.UUID(settings.default_storage_user_id))
    try:

        class _Ctx:
            client_id = settings.default_storage_user_id

        result = await _mcp_tool("get_day")(date=str(committed_day), ctx=_Ctx())
    finally:
        user_id_ctx.reset(tok)
    assert result is not None
    assert result["date"] == str(committed_day)
    assert result["notes"] == "regression day"
    assert [m.get("name") or m.get("label") for m in result["meals"]] == ["Oats"] or len(
        result["meals"]
    ) == 1


@pytest.mark.asyncio
async def test_list_days_end_to_end_after_session_close(
    committed_day, real_scoped_sessions
) -> None:
    class _Ctx:
        client_id = settings.default_storage_user_id

    result = await _mcp_tool("list_days")(
        start_date=str(committed_day), end_date=str(committed_day), ctx=_Ctx()
    )
    assert [d["date"] for d in result["days"]] == [str(committed_day)]
    assert result["days"][0]["meal_count"] == 1


@pytest.mark.asyncio
async def test_treatments_end_to_end_after_session_close(
    committed_day, real_scoped_sessions
) -> None:
    class _Ctx:
        client_id = settings.default_storage_user_id

    result = await _mcp_tool("treatments")(on_date=str(committed_day), recent_days=3, ctx=_Ctx())
    assert any(i["name"] == "Regression-Tx" for i in result["protocol"]["items"])
    assert result["recent_doses"] and result["recent_doses"][0]["doses_taken"] == 1
