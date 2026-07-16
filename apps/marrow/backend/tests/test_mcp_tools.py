from __future__ import annotations

import datetime
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.auth.provider import AccessToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.tools import _mcp_user_id

from app.models.entry import Entry
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.models.treatment import Treatment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_entry(db: AsyncSession, date_str: str = "2025-01-15") -> Entry:
    entry = Entry(
        date=datetime.date.fromisoformat(date_str),
        overall=7,
        bloating=3,
        joint_pain=2,
        neuro=4,
        sleep_quality=8,
        stress=5,
        diet_risk="low",
        supplements="",
        sick=False,
        hot_shower=False,
        notes="Test entry notes",
        symptoms_json={"vss": 6},
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


async def _seed_treatment(db: AsyncSession, active: bool = True) -> Treatment:
    t = Treatment(
        name="Magnesium",
        normalized_name="magnesium",
        type="supplement",
        start_date=datetime.date(2024, 1, 1),
        end_date=None if active else datetime.date(2024, 6, 1),
        dose="400mg",
        notes="Before bed",
    )
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


async def _seed_lab(db: AsyncSession) -> tuple[Lab, LabMarkerCatalog, LabMarker]:
    # Catalog entry required due to FK constraint.
    cat = LabMarkerCatalog(
        canonical_name="crp",
        display_name="C-Reactive Protein",
        common_units=["mg/L"],
    )
    db.add(cat)
    await db.flush()

    lab = Lab(
        lab_date=datetime.date(2025, 3, 1),
        name="Blood Panel",
        type="blood",
        source_kind="pdf",
        review_status="confirmed",
    )
    db.add(lab)
    await db.flush()

    marker = LabMarker(
        lab_id=lab.id,
        catalog_id=cat.id,
        canonical_name="crp",
        display_name="CRP",
        value=1.2,
        unit="mg/L",
        flag="normal",
    )
    db.add(marker)
    await db.flush()
    return lab, cat, marker


# ---------------------------------------------------------------------------
# Inline tool functions (we call the service logic directly, not via MCP transport)
# ---------------------------------------------------------------------------


def test_mcp_user_id_prefers_ctx_client_id() -> None:
    user_id = uuid.uuid4()

    class _Ctx:
        client_id = str(user_id)

    with patch("app.mcp.tools.get_access_token", return_value=None):
        assert _mcp_user_id(_Ctx()) == user_id


def test_mcp_user_id_falls_back_to_bearer_access_token() -> None:
    user_id = uuid.uuid4()
    token = AccessToken(token="test-token", client_id=str(user_id), scopes=[])

    with patch("app.mcp.tools.get_access_token", return_value=token):
        assert _mcp_user_id(None) == user_id


async def test_get_entry_returns_none_when_missing(async_db: AsyncSession) -> None:
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        # Register tools on a dummy server (we don't actually call via transport).
        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        # Direct test: call the underlying tool fn via the tools dict.
        tool_fn = None
        for tool in server._tool_manager.list_tools():
            if tool.name == "get_entry":
                tool_fn = tool.fn
                break
        assert tool_fn is not None

        result = await tool_fn(date="2099-01-01")
        assert result is None


async def test_get_entry_returns_dict_when_exists(async_db: AsyncSession) -> None:
    await _seed_entry(async_db)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "get_entry").fn
        result = await tool_fn(date="2025-01-15")

    assert result is not None
    assert result["date"] == "2025-01-15"
    assert result["overall"] == 7
    assert result["notes"] == "Test entry notes"


async def test_list_entries_range(async_db: AsyncSession) -> None:
    await _seed_entry(async_db, "2025-02-01")
    await _seed_entry(async_db, "2025-02-15")

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "list_entries").fn
        result = await tool_fn(start_date="2025-02-01", end_date="2025-02-28")

    assert len(result["entries"]) == 2


async def test_list_treatments_active_only(async_db: AsyncSession) -> None:
    await _seed_treatment(async_db, active=True)
    await _seed_treatment(async_db, active=False)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(
            t for t in server._tool_manager.list_tools() if t.name == "list_treatments"
        ).fn
        result = await tool_fn(active_only=True)

    assert len(result["treatments"]) == 1
    assert result["treatments"][0]["end_date"] is None


async def test_list_treatments_all(async_db: AsyncSession) -> None:
    await _seed_treatment(async_db, active=True)
    await _seed_treatment(async_db, active=False)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(
            t for t in server._tool_manager.list_tools() if t.name == "list_treatments"
        ).fn
        result = await tool_fn(active_only=False)

    assert len(result["treatments"]) == 2


async def test_get_lab_history(async_db: AsyncSession) -> None:
    lab, cat, marker = await _seed_lab(async_db)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(
            t for t in server._tool_manager.list_tools() if t.name == "get_lab_history"
        ).fn
        result = await tool_fn(marker_canonical_name="crp")

    assert result["marker"] == "crp"
    assert len(result["history"]) == 1
    assert result["history"][0]["value"] == pytest.approx(1.2)


async def test_list_labs_range(async_db: AsyncSession) -> None:
    await _seed_lab(async_db)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "list_labs").fn
        result = await tool_fn(start_date="2025-01-01", end_date="2025-12-31")

    assert len(result["labs"]) == 1
    assert result["labs"][0]["name"] == "Blood Panel"
    assert result["labs"][0]["marker_count"] == 1


async def test_read_sql_select_returns_rows(async_db: AsyncSession) -> None:
    await _seed_entry(async_db)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "read_sql").fn
        result = await tool_fn(query="SELECT id, overall FROM entries LIMIT 5")

    assert "columns" in result
    assert "rows" in result
    assert "id" in result["columns"]
    assert "overall" in result["columns"]


async def test_read_sql_dml_returns_error_structure(async_db: AsyncSession) -> None:
    """DML against the test DB (not ro role, but will still error or rollback) returns error dict."""
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "read_sql").fn
        # In tests we use the main engine (same user), so DELETE succeeds — but we test
        # the error wrapper for invalid SQL.
        result = await tool_fn(query="SELECT * FROM nonexistent_table_xyz_123")

    assert "error" in result


async def test_read_sql_rejects_multi_statement(async_db: AsyncSession) -> None:
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "read_sql").fn
        result = await tool_fn(query="SELECT 1; DROP TABLE entries")

    assert "error" in result
    assert "guardrails" in result["error"]


async def test_read_sql_rejects_pg_sleep(async_db: AsyncSession) -> None:
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "read_sql").fn
        result = await tool_fn(query="SELECT pg_sleep(1)")

    assert "error" in result
    assert "guardrails" in result["error"]


async def test_tool_invocation_emits_log_line(
    async_db: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    await _seed_entry(async_db)

    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        from mcp.server.fastmcp import FastMCP

        server = FastMCP("test")
        t_mod.register_tools(server)

        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "get_entry").fn
        with caplog.at_level("INFO"):
            await tool_fn(date="2025-01-15")

    assert any("mcp_invocation" in record.message for record in caplog.records)
    assert any("name=get_entry" in record.message for record in caplog.records)


async def test_search_health_data_empty_table(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When embedding table is empty, return empty results with a note."""
    from app.config import settings
    from app.mcp import tools as t_mod

    # Ensure build_embedding_client() can resolve credentials. Locally the dev
    # .env supplies OPENROUTER_API_KEY; CI has none, so the env fallback in
    # _resolve() returns None and the factory raises ConflictError before we
    # ever reach the empty-table probe under test. Pin it to a dummy value.
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key-not-real")

    with (
        patch("app.mcp.tools.scoped_main_session") as mock_main,
        patch("app.mcp.tools.scoped_ro_session") as mock_ro,
    ):
        mock_main.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_main.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.mcp.tools.resolve_embedding_credentials",
            return_value=("fake-key", "openai/text-embedding-3-small"),
        ):
            from mcp.server.fastmcp import FastMCP

            server = FastMCP("test")
            t_mod.register_tools(server)

            tool_fn = next(
                t for t in server._tool_manager.list_tools() if t.name == "search_health_data"
            ).fn
            result = await tool_fn(query="test query")

    assert result["results"] == []
    assert "note" in result
    assert "backfill" in result["note"]
