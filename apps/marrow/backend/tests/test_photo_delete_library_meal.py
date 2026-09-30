"""Regression: deleting an MCP/library-created meal (no file, tags, ingredients)."""

from __future__ import annotations

import contextlib
import uuid
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp import tools as t_mod
from app.models.meal import Meal
from app.models.meal_tag import MealTag
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from f0rge_db.tenant import apply_session_user_id, user_id_ctx
from tests.test_social_meal_tags import (
    DAY,
    _connect_users,
    _signup_client,
    _user_id,
    patch_tag_delivery_maker,  # noqa: F401  (fixture)
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def isolated_storage(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    patch_tag_delivery_maker: None,  # noqa: F811
) -> None:
    photo_dir = tmp_path / "photos"
    photo_dir.mkdir()
    monkeypatch.setattr(settings, "photo_dir", str(photo_dir))
    monkeypatch.setattr(settings, "food_analysis_enabled", False)


@contextlib.asynccontextmanager
async def _mcp_server_as(db: AsyncSession, user_id: uuid.UUID) -> AsyncIterator[FastMCP]:
    """MCP server whose main session is the shared test session, scoped to ``user_id``."""
    token = user_id_ctx.set(user_id)
    try:
        await apply_session_user_id(db, user_id)
        with patch(
            "app.mcp.tools.scoped_main_session",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=db),
                __aexit__=AsyncMock(return_value=False),
            ),
        ):
            server = FastMCP("test")
            t_mod.register_tools(server)
            yield server
    finally:
        user_id_ctx.reset(token)


def _tool_fn(server: FastMCP, name: str):
    return next(t for t in server._tool_manager.list_tools() if t.name == name).fn


async def _count(db: AsyncSession, model: type) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _owned_meal_count(db: AsyncSession, owner_id: uuid.UUID) -> int:
    """Meals owned by ``owner_id`` only — other tests leave committed meals behind."""
    stmt = select(func.count()).select_from(Meal).where(Meal.owner_user_id == owner_id)
    return (await db.execute(stmt)).scalar_one()


async def _seed_mcp_meal_with_tag(
    db: AsyncSession, owner: AsyncClient, bea: AsyncClient, *, auto_accept: bool
) -> dict[str, Any]:
    """MCP ``log_meal`` (no photo file) with ingredients, tagged with a connected user.

    ``auto_accept``: Bea's tag is ``delivered`` and she holds her own placement (photo
    row) sharing the owner's meal -- the "With @bea" case from production. Otherwise
    the tag stays ``pending_approval``.
    """
    await _connect_users(owner, bea)
    bea_handle = (await bea.get("/api/v1/auth/me")).json()["handle"]
    mode = "auto" if auto_accept else "manual"
    await bea.put("/api/v1/settings/tagged-meal-mode", json={"tagged_meal_mode": mode})
    async with _mcp_server_as(db, await _user_id(owner)) as server:
        logged = await _tool_fn(server, "log_meal")(
            date=DAY.isoformat(),
            name="MCP live pasta",
            meal_time="12:30",
            ingredients=["pasta", "tomato"],
        )
        await _tool_fn(server, "tag_meal")(photo_id=logged["photo_id"], handles=[bea_handle])
    tag_status = (await db.execute(select(MealTag.status))).scalar_one()
    assert tag_status == ("delivered" if auto_accept else "pending_approval")
    return logged


async def _bea_meal_count(bea: AsyncClient) -> int:
    return len((await bea.get("/api/v1/photos?scope=tagged")).json())


@pytest.mark.parametrize("auto_accept", [False, True], ids=["pending_tag", "delivered_tag"])
async def test_delete_endpoint_removes_mcp_meal_without_photo(
    async_db: AsyncSession, isolated_storage: None, auto_accept: bool
) -> None:
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    bea = await _signup_client(async_db, uuid.uuid4().hex[:6])
    logged = await _seed_mcp_meal_with_tag(async_db, owner, bea, auto_accept=auto_accept)
    assert logged["has_photo"] is False
    assert await _count(async_db, PhotoIngredient) == 2

    resp = await owner.delete(f"/api/v1/photos/{logged['photo_id']}")

    assert resp.status_code == 204, resp.text
    assert (await owner.get("/api/v1/photos")).json() == []
    assert await _count(async_db, MealTag) == 0
    if auto_accept:
        # Bea's delivered placement still points at the shared meal + analysis.
        assert await _bea_meal_count(bea) == 1
        assert await _count(async_db, PhotoIngredient) == 2
    else:
        assert await _owned_meal_count(async_db, await _user_id(owner)) == 0
        assert await _count(async_db, PhotoAnalysis) == 0
        assert await _count(async_db, PhotoIngredient) == 0


@pytest.mark.parametrize("auto_accept", [False, True], ids=["pending_tag", "delivered_tag"])
async def test_mcp_delete_meal_removes_meal_without_photo(
    async_db: AsyncSession, isolated_storage: None, auto_accept: bool
) -> None:
    owner = await _signup_client(async_db, uuid.uuid4().hex[:6])
    bea = await _signup_client(async_db, uuid.uuid4().hex[:6])
    logged = await _seed_mcp_meal_with_tag(async_db, owner, bea, auto_accept=auto_accept)

    async with _mcp_server_as(async_db, await _user_id(owner)) as server:
        out = await _tool_fn(server, "delete_meal")(photo_id=logged["photo_id"])

    assert out == {"photo_id": logged["photo_id"], "deleted": True}
    assert (await owner.get("/api/v1/photos")).json() == []
    assert await _count(async_db, MealTag) == 0
    if auto_accept:
        assert await _bea_meal_count(bea) == 1
    else:
        assert await _owned_meal_count(async_db, await _user_id(owner)) == 0
        assert await _count(async_db, PhotoIngredient) == 0
