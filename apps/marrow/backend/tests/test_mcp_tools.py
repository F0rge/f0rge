from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.tools import _mcp_user_id

from app.models.entry import Entry
from app.models.lab import Lab
from app.models.lab_marker import LabMarker
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.models.treatment import Treatment


async def _seed_entry(db: AsyncSession, date_str: str = "2025-01-15") -> Entry:
    import datetime

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
    import datetime

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
    import datetime

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


async def test_get_day_returns_none_when_missing(async_db: AsyncSession) -> None:
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        server = FastMCP("test")
        t_mod.register_tools(server)
        tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "get_day").fn
        result = await tool_fn(date="2099-01-01")
        assert result is None


async def test_get_lab_history(async_db: AsyncSession) -> None:
    await _seed_lab(async_db)
    from app.mcp import tools as t_mod

    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        server = FastMCP("test")
        t_mod.register_tools(server)
        tool_fn = next(
            t for t in server._tool_manager.list_tools() if t.name == "get_lab_history"
        ).fn
        result = await tool_fn(marker_canonical_name="crp")

    assert result["marker"] == "crp"
    assert len(result["history"]) == 1


async def test_search_empty_table(
    async_db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.mcp import tools as t_mod

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
            server = FastMCP("test")
            t_mod.register_tools(server)
            tool_fn = next(t for t in server._tool_manager.list_tools() if t.name == "search").fn
            result = await tool_fn(query="test query")

    assert result["results"] == []
    assert "note" in result
