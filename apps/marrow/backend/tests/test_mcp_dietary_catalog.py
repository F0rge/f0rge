"""End-to-end tests for the ``marrow://catalog/dietary-ingredients`` MCP resource.

Uses real (committed) rows and ``real_scoped_sessions`` so the scoped RO session opens and
closes exactly like production (payloads must not touch ORM rows after the session closes).
"""

from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

import pytest
import sqlalchemy as sa
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.mcp.resources import dietary_catalog as catalog_mod
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session

from tests.test_mcp_database import real_scoped_sessions  # noqa: F401  (fixture)

_LEO = uuid.UUID(settings.default_storage_user_id)


def _resource_fn():
    from app.mcp import resources as resources_mod

    server = FastMCP("test")
    resources_mod.register_resources(server)
    return next(
        r
        for r in server._resource_manager.list_resources()
        if str(r.uri) == "marrow://catalog/dietary-ingredients"
    ).fn


async def _read_as(user_id: uuid.UUID) -> dict[str, Any]:
    token = user_id_ctx.set(user_id)
    try:
        return await _resource_fn()()
    finally:
        user_id_ctx.reset(token)


async def _add_ingredient(
    session: AsyncSession, user_id: uuid.UUID, name: str, **overrides: Any
) -> None:
    from app.models.dietary_ingredient import DietaryIngredient

    values: dict[str, Any] = {
        "category": "grains",
        "histamine_score": 0,
        "fodmap_oligos": "low",
        "fodmap_fructose": "low",
        "fodmap_polyols": "low",
        "fodmap_lactose": "low",
        "contains_gluten": False,
        "contains_dairy": False,
    }
    values.update(overrides)
    session.add(DietaryIngredient(user_id=user_id, canonical_name=name, **values))
    await session.flush()


@pytest.fixture
async def two_user_catalogs(superuser_engine, async_engine) -> AsyncIterator[uuid.UUID]:
    """Committed catalogues for Leo and a second user; yields the second user's id."""
    from app.models.ingredient_alias import IngredientAlias

    other = uuid.uuid4()
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, avatar_default_index, created_at) "
                "VALUES (:id, :email, 'x', 0, now())"
            ),
            {"id": other, "email": f"catalog-{other}@test.local"},
        )
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    async with maker() as s:
        await apply_session_user_id(s, _LEO)
        await _add_ingredient(s, _LEO, "zz-oats", histamine_score=0)
        await _add_ingredient(s, _LEO, "zz-wheat flour", contains_gluten=True, fodmap_oligos="high")
        await _add_ingredient(s, _LEO, "zz-old thing", category="other", archived=True)
        await s.flush()
        s.add(IngredientAlias(user_id=_LEO, alias="zz-rolled oats", canonical_name="zz-oats"))
        await s.commit()
        await clear_tenant_session(s)
    async with maker() as s:
        await apply_session_user_id(s, other)
        await _add_ingredient(s, other, "zz-secret-only-other-user")
        await s.commit()
        await clear_tenant_session(s)
    try:
        yield other
    finally:
        async with superuser_engine.begin() as conn:
            await conn.execute(
                sa.text("DELETE FROM ingredient_aliases WHERE canonical_name LIKE 'zz-%'")
            )
            await conn.execute(
                sa.text("DELETE FROM dietary_ingredients WHERE canonical_name LIKE 'zz-%'")
            )
            await conn.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": other})


@pytest.mark.usefixtures("real_scoped_sessions")
async def test_resource_lists_active_entries_with_aliases_and_flags(
    two_user_catalogs,
) -> None:
    result = await _read_as(_LEO)
    by_name = {i["canonical_name"]: i for i in result["ingredients"]}

    assert result["count"] == len(result["ingredients"])
    assert result["truncated"] is False
    oats = by_name["zz-oats"]
    assert oats["aliases"] == ["zz-rolled oats"]
    assert oats["flags"]["contains_gluten"] is False
    assert oats["flags"]["fodmap"] == {
        "oligos": "low",
        "fructose": "low",
        "polyols": "low",
        "lactose": "low",
    }
    flour = by_name["zz-wheat flour"]
    assert flour["flags"]["contains_gluten"] is True
    assert flour["flags"]["high_fodmap"] is True
    assert flour["flags"]["high_histamine"] is False
    assert flour["category"] == "grains"


@pytest.mark.usefixtures("real_scoped_sessions")
async def test_resource_excludes_archived_ingredients(
    two_user_catalogs,
) -> None:
    names = {i["canonical_name"] for i in (await _read_as(_LEO))["ingredients"]}
    assert "zz-oats" in names
    assert "zz-old thing" not in names


@pytest.mark.usefixtures("real_scoped_sessions")
async def test_resource_is_tenant_scoped(
    two_user_catalogs,
) -> None:
    other = two_user_catalogs
    leo_names = {i["canonical_name"] for i in (await _read_as(_LEO))["ingredients"]}
    other_names = {i["canonical_name"] for i in (await _read_as(other))["ingredients"]}

    assert "zz-secret-only-other-user" not in leo_names
    assert other_names == {"zz-secret-only-other-user"}
    assert "zz-oats" not in other_names


@pytest.mark.usefixtures("real_scoped_sessions")
async def test_resource_caps_size_and_reports_truncation(
    two_user_catalogs,
    monkeypatch,
) -> None:
    monkeypatch.setattr(catalog_mod, "DIETARY_CATALOG_RESOURCE_MAX", 1)
    result = await _read_as(_LEO)
    assert result["count"] == 1
    assert len(result["ingredients"]) == 1
    assert result["truncated"] is True
