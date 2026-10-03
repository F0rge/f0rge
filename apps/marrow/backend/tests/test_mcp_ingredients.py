"""End-to-end tests for ingredient search + catalogue-aware logging through the MCP tools.

Real committed rows and ``real_scoped_sessions`` (real open/close semantics, RLS enforced as the
NOSUPERUSER test_app role), following tests/test_mcp_database.py.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, AsyncIterator

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.mcp import ingredient_logging
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from f0rge_core.exceptions import ValidationError
from f0rge_db.auth_context import user_id_ctx
from f0rge_db.tenant import apply_session_user_id, clear_tenant_session
from tests.test_mcp_database import _mcp_tool, real_scoped_sessions  # noqa: F401

_LEO = uuid.UUID(settings.default_storage_user_id)
_DAY = "2031-05-06"
_NAMES = (
    "oats",
    "sunflower oil",
    "raisin",
    "dried apricot",
    "almonds",
    "muesli",
    "wheat flour",
    "oat milk",
    "archived thing",
)

pytestmark = pytest.mark.usefixtures("real_scoped_sessions")


class _Ctx:
    def __init__(self, user_id: uuid.UUID = _LEO) -> None:
        self.client_id = str(user_id)


async def _call(tool: str, user_id: uuid.UUID = _LEO, **kwargs: Any) -> Any:
    token = user_id_ctx.set(user_id)
    try:
        return await _mcp_tool(tool)(ctx=_Ctx(user_id), **kwargs)
    finally:
        user_id_ctx.reset(token)


def _ing(name: str, **overrides: Any) -> dict[str, Any]:
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
    return {"canonical_name": name, **values}


async def _wipe(superuser_engine, user_ids: list[uuid.UUID]) -> None:
    day = datetime.date.fromisoformat(_DAY)
    photo_ids = "SELECT p.id FROM photos p JOIN entries e ON e.id = p.entry_id WHERE e.date = :d"
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "DELETE FROM photo_ingredients WHERE analysis_id IN "
                f"(SELECT id FROM photo_analyses WHERE photo_id IN ({photo_ids}))"
            ),
            {"d": day},
        )
        await conn.execute(
            sa.text(f"DELETE FROM photo_analyses WHERE photo_id IN ({photo_ids})"), {"d": day}
        )
        await conn.execute(
            sa.text(
                "DELETE FROM photos WHERE entry_id IN (SELECT id FROM entries WHERE date = :d)"
            ),
            {"d": day},
        )
        await conn.execute(sa.text("DELETE FROM meals WHERE label LIKE 'zz-%'"))
        await conn.execute(sa.text("DELETE FROM entries WHERE date = :d"), {"d": day})
        await conn.execute(
            sa.text("DELETE FROM ingredient_aliases WHERE user_id = ANY(:u)"), {"u": user_ids}
        )
        await conn.execute(
            sa.text("DELETE FROM dietary_ingredients WHERE user_id = ANY(:u)"), {"u": user_ids}
        )


@pytest.fixture
async def catalogue(superuser_engine, async_engine) -> AsyncIterator[uuid.UUID]:
    """Committed catalogues: Leo (oats+alias, sunflower oil, raisin, ..., archived) and another
    user with a private ``quinoa``. Yields the other user's id."""
    other = uuid.uuid4()
    await _wipe(superuser_engine, [_LEO])
    async with superuser_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, avatar_default_index, created_at) "
                "VALUES (:id, :email, 'x', 0, now())"
            ),
            {"id": other, "email": f"ingr-{other}@test.local"},
        )
    maker = async_sessionmaker(async_engine, expire_on_commit=False)
    async with maker() as s:
        await apply_session_user_id(s, _LEO)
        for item in (
            _ing("oats"),
            _ing("sunflower oil", category="oils", histamine_score=0),
            _ing("raisin", category="fruit", histamine_score=1, fodmap_oligos="high"),
            _ing("dried apricot", category="fruit", histamine_score=2),
            _ing("almonds", category="nuts_seeds", histamine_score=1, fodmap_oligos="high"),
            _ing("muesli", contains_gluten=True),
            _ing("wheat flour", contains_gluten=True, fodmap_oligos="high"),
            _ing("oat milk", category="dairy_alternatives"),
            _ing("archived thing", archived=True),
        ):
            s.add(DietaryIngredient(user_id=_LEO, **item))
        await s.flush()
        s.add(IngredientAlias(user_id=_LEO, alias="rolled oats", canonical_name="oats"))
        await s.commit()
        await clear_tenant_session(s)
    async with maker() as s:
        await apply_session_user_id(s, other)
        s.add(DietaryIngredient(user_id=other, **_ing("quinoa")))
        await s.commit()
        await clear_tenant_session(s)
    try:
        yield other
    finally:
        await _wipe(superuser_engine, [_LEO, other])
        async with superuser_engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": other})


# --------------------------------------------------------------------------- search_ingredients


async def test_search_exact_alias_and_flags(catalogue) -> None:
    exact = await _call("search_ingredients", query="raisin")
    top = exact["results"][0]
    assert (top["canonical_name"], top["match_type"], top["score"]) == ("raisin", "exact", 1.0)
    assert top["flags"]["histamine_score"] == 1
    assert top["flags"]["fodmap"]["oligos"] == "high"
    assert top["flags"]["high_fodmap"] is True
    assert top["flags"]["contains_gluten"] is False

    alias = await _call("search_ingredients", query="Rolled Oats")
    top = alias["results"][0]
    assert (top["canonical_name"], top["match_type"], top["matched_alias"]) == (
        "oats",
        "alias",
        "rolled oats",
    )


async def test_search_singular_plural_and_quantity(catalogue) -> None:
    for query in ("raisins", "almond", "oat", "oats (40 g)"):
        result = await _call("search_ingredients", query=query)
        top = result["results"][0]
        assert top["match_type"] in {"alias", "normalised"}, query
        assert (
            top["canonical_name"]
            == {
                "raisins": "raisin",
                "almond": "almonds",
                "oat": "oats",
                "oats (40 g)": "oats",
            }[query]
        )


async def test_search_token_subset_fuzzy_prefix_and_partial(catalogue) -> None:
    subset = await _call("search_ingredients", query="gluten-free rolled oats")
    assert subset["results"][0]["canonical_name"] == "oats"
    assert subset["results"][0]["match_type"] == "token_subset"

    fuzzy = await _call("search_ingredients", query="sunflwer oil")
    assert (fuzzy["results"][0]["canonical_name"], fuzzy["results"][0]["match_type"]) == (
        "sunflower oil",
        "fuzzy",
    )

    partial = await _call("search_ingredients", query="sunflower")
    assert partial["results"][0]["canonical_name"] == "sunflower oil"
    assert partial["results"][0]["match_type"] in {"partial", "prefix"}


async def test_search_limit_caps_and_orders_results(catalogue) -> None:
    result = await _call("search_ingredients", query="oat", limit=1)
    assert len(result["results"]) == 1
    wide = await _call("search_ingredients", query="oat", limit=500)
    assert len(wide["results"]) <= 25
    scores = [r["score"] for r in wide["results"]]
    assert scores == sorted(scores, reverse=True)
    assert wide["count"] == len(wide["results"])


async def test_search_excludes_archived_and_other_users(catalogue) -> None:
    archived = await _call("search_ingredients", query="archived thing")
    assert "archived thing" not in {r["canonical_name"] for r in archived["results"]}

    other_user_item = await _call("search_ingredients", query="quinoa")
    assert other_user_item["results"] == []

    other = catalogue
    theirs = await _call("search_ingredients", user_id=other, query="quinoa")
    assert theirs["results"][0]["canonical_name"] == "quinoa"
    leaked = await _call("search_ingredients", user_id=other, query="oats")
    assert leaked["results"] == []


async def test_search_requires_query_and_flags_composites(catalogue) -> None:
    with pytest.raises(ValidationError):
        await _call("search_ingredients", query="   ")
    composite = await _call(
        "search_ingredients", query="Auchan gluten-free crunchy dried fruit muesli (40 g)"
    )
    assert composite["composite_suspected"] is True
    assert "constituent" in composite["composite_hint"]
    assert any(r["canonical_name"] == "muesli" for r in composite["results"])


# --------------------------------------------------------------------------- log_meal


async def test_log_meal_decomposed_ingredients_match_with_flags(catalogue) -> None:
    result = await _call(
        "log_meal",
        date=_DAY,
        name="zz-Auchan muesli, 40 g",
        meal_time="08:00",
        ingredients=["oats", "sunflower oil", "raisin", "dried apricots", "rolled oats"],
    )
    assert result["ingredient_count"] == 5
    assert result["matched_count"] == 5
    assert result["unmatched"] == [] and result["approximate"] == []
    by_name = {i["name"]: i for i in result["ingredients"]}
    assert by_name["oats"]["match"]["status"] == "exact"
    assert by_name["rolled oats"]["match"]["status"] == "alias"
    assert by_name["rolled oats"]["canonical_name"] == "oats"
    assert by_name["dried apricots"]["match"]["status"] == "normalised"
    assert by_name["dried apricots"]["canonical_name"] == "dried apricot"
    assert by_name["raisin"]["histamine_score"] == 1
    assert by_name["raisin"]["fodmap_oligos"] == "high"
    assert by_name["dried apricots"]["histamine_score"] == 2
    assert by_name["raisin"]["flags"]["high_fodmap"] is True
    assert "matched the catalogue" in result["next_step"]

    meal = await _call("get_meal", photo_id=result["photo_id"])
    stored = {i["name"]: i for i in meal["analysis"]["ingredients"]}
    assert stored["raisin"]["fodmap_oligos"] == "high"
    assert stored["oats"]["contains_gluten"] is False


async def test_log_meal_auchan_product_string_is_unmatched_with_hint(catalogue) -> None:
    product = "Auchan gluten-free crunchy dried fruit muesli (40 g)"
    result = await _call("log_meal", date=_DAY, name="zz-product", ingredients=[product])
    [ingredient] = result["ingredients"]
    assert ingredient["match"]["status"] == "unmatched"
    assert ingredient["canonical_name"] is None
    assert ingredient["flags"] is None
    assert ingredient["contains_gluten"] is None and ingredient["histamine_score"] is None
    assert ingredient["match"]["composite_suspected"] is True
    assert "constituent" in ingredient["match"]["composite_hint"]
    assert "muesli" in {s["canonical_name"] for s in ingredient["match"]["suggestions"]}
    assert result["unmatched"] == [product]
    assert result["composite_suspected"] == [product]
    assert result["matched_count"] == 0
    assert "search_ingredients" in result["next_step"]
    # Stored (logging is never blocked), without silently borrowing muesli's gluten flag.
    meal = await _call("get_meal", photo_id=result["photo_id"])
    [stored] = meal["analysis"]["ingredients"]
    assert stored["name"] == product and stored["contains_gluten"] is None


async def test_log_meal_approximate_match_is_not_flagged(catalogue) -> None:
    result = await _call(
        "log_meal",
        date=_DAY,
        name="zz-approx",
        ingredients=["gluten-free rolled oats", "wheat flour"],
    )
    by_name = {i["name"]: i for i in result["ingredients"]}
    approx = by_name["gluten-free rolled oats"]
    assert approx["match"]["status"] == "approximate"
    assert approx["match"]["flags_attached"] is False
    assert approx["canonical_name"] is None
    assert approx["contains_gluten"] is None
    assert approx["match"]["suggestions"][0]["canonical_name"] == "oats"
    assert by_name["wheat flour"]["contains_gluten"] is True
    assert result["approximate"] == ["gluten-free rolled oats"]
    assert result["matched_count"] == 1
    assert "approximately" in result["next_step"]


async def test_log_meal_archived_ingredient_is_unmatched(catalogue) -> None:
    result = await _call("log_meal", date=_DAY, name="zz-arch", ingredients=["archived thing"])
    [ingredient] = result["ingredients"]
    assert ingredient["match"]["status"] == "unmatched"
    assert ingredient["canonical_name"] is None


async def test_log_meal_other_users_catalogue_is_invisible(catalogue) -> None:
    result = await _call("log_meal", date=_DAY, name="zz-quinoa", ingredients=["quinoa"])
    assert result["ingredients"][0]["match"]["status"] == "unmatched"
    assert result["ingredients"][0]["match"]["suggestions"] == []


async def test_log_meal_dedupes_and_enforces_cap_before_writing(catalogue) -> None:
    result = await _call(
        "log_meal", date=_DAY, name="zz-dupes", ingredients=["oats", "Oats", "  ", "raisin"]
    )
    assert [i["name"] for i in result["ingredients"]] == ["oats", "raisin"]
    assert result["duplicates_dropped"] == ["Oats"]

    too_many = [f"thing {i}" for i in range(41)]
    with pytest.raises(ValidationError):
        await _call("log_meal", date=_DAY, name="zz-too-many", ingredients=too_many)
    days = await _call("get_day", date=_DAY)
    assert [m["name"] for m in days["meals"]].count("zz-too-many") == 0


async def test_ingredient_tool_payloads_are_json_serialisable(catalogue) -> None:
    import json

    logged = await _call(
        "log_meal", date=_DAY, name="zz-json", ingredients=["oats", "gluten-free rolled oats", "x"]
    )
    json.dumps(logged)
    json.dumps(await _call("set_ingredients", photo_id=logged["photo_id"], ingredients=["oats"]))
    json.dumps(await _call("search_ingredients", query="oat"))


async def test_log_meal_without_ingredients_still_works(catalogue) -> None:
    result = await _call("log_meal", date=_DAY, name="zz-none")
    assert result["ingredient_count"] == 0 and result["ingredients"] == []
    assert "No ingredients" in result["next_step"]


# --------------------------------------------------------------------------- set_ingredients


async def test_set_ingredients_product_then_decomposed_flow(catalogue) -> None:
    product = "Auchan gluten-free crunchy dried fruit muesli (40 g)"
    logged = await _call("log_meal", date=_DAY, name="zz-flow", ingredients=[product])
    photo_id = logged["photo_id"]

    first = await _call("set_ingredients", photo_id=photo_id, ingredients=[product])
    assert first["unmatched"] == [product]
    assert first["ingredients"][0]["match"]["status"] == "unmatched"

    fixed = await _call(
        "set_ingredients",
        photo_id=photo_id,
        ingredients=["oats", "sunflower oil", "raisin", "dried apricot", "almonds"],
    )
    assert fixed["ingredient_count"] == 5 and fixed["matched_count"] == 5
    assert fixed["unmatched"] == [] and fixed["approximate"] == []
    assert all(i["match"]["status"] == "exact" for i in fixed["ingredients"])
    assert "matched the catalogue" in fixed["next_step"]

    meal = await _call("get_meal", photo_id=photo_id)
    names = sorted(i["name"] for i in meal["analysis"]["ingredients"])
    assert names == ["almonds", "dried apricot", "oats", "raisin", "sunflower oil"]
    assert all(i["canonical_name"] for i in meal["analysis"]["ingredients"])


async def test_set_ingredients_is_atomic_when_a_row_fails(catalogue, monkeypatch) -> None:
    """A DB-level failure on the 2nd new row (NOT NULL violation at flush) must roll back the
    delete of the old list and the insert of the 1st new row: all or nothing."""
    logged = await _call("log_meal", date=_DAY, name="zz-atomic", ingredients=["oats", "raisin"])
    photo_id = logged["photo_id"]

    real_build = ingredient_logging.build_ingredient_row
    calls = {"n": 0}

    def poisoned_build(*args: Any, **kwargs: Any):
        row = real_build(*args, **kwargs)
        calls["n"] += 1
        if calls["n"] == 2:
            row.confidence = None  # photo_ingredients.confidence is NOT NULL
        return row

    monkeypatch.setattr(ingredient_logging, "build_ingredient_row", poisoned_build)
    with pytest.raises(sa.exc.DBAPIError):
        await _call(
            "set_ingredients", photo_id=photo_id, ingredients=["almonds", "muesli", "wheat flour"]
        )
    monkeypatch.undo()

    meal = await _call("get_meal", photo_id=photo_id)
    assert sorted(i["name"] for i in meal["analysis"]["ingredients"]) == ["oats", "raisin"]


async def test_set_ingredients_validation_failure_keeps_old_list(catalogue) -> None:
    logged = await _call("log_meal", date=_DAY, name="zz-keep", ingredients=["oats"])
    with pytest.raises(ValidationError):
        await _call(
            "set_ingredients",
            photo_id=logged["photo_id"],
            ingredients=[f"thing {i}" for i in range(41)],
        )
    meal = await _call("get_meal", photo_id=logged["photo_id"])
    assert [i["name"] for i in meal["analysis"]["ingredients"]] == ["oats"]


async def test_set_ingredients_empty_list_clears(catalogue) -> None:
    logged = await _call("log_meal", date=_DAY, name="zz-clear", ingredients=["oats"])
    cleared = await _call("set_ingredients", photo_id=logged["photo_id"], ingredients=[])
    assert cleared["ingredient_count"] == 0
    meal = await _call("get_meal", photo_id=logged["photo_id"])
    assert meal["analysis"]["ingredients"] == []


async def test_set_ingredients_other_users_meal_is_not_found(catalogue) -> None:
    from f0rge_core.exceptions import NotFoundError

    logged = await _call("log_meal", date=_DAY, name="zz-private", ingredients=["oats"])
    with pytest.raises(NotFoundError):
        await _call(
            "set_ingredients", user_id=catalogue, photo_id=logged["photo_id"], ingredients=["x"]
        )


async def test_set_ingredients_uses_callers_catalogue_not_others(catalogue) -> None:
    other = catalogue
    mine = await _call("log_meal", date=_DAY, name="zz-mine", ingredients=["oats"])
    result = await _call(
        "set_ingredients", photo_id=mine["photo_id"], ingredients=["quinoa", "oats"]
    )
    by_name = {i["name"]: i for i in result["ingredients"]}
    assert by_name["quinoa"]["match"]["status"] == "unmatched"
    assert by_name["oats"]["match"]["status"] == "exact"
    assert other != _LEO


async def test_tool_descriptions_mention_search_ingredients() -> None:
    from mcp.server.fastmcp import FastMCP

    from app.mcp import tools as t_mod

    server = FastMCP("test")
    t_mod.register_tools(server)
    desc = {t.name: t.description for t in server._tool_manager.list_tools()}
    for name in ("log_meal", "set_ingredients", "edit_meal"):
        assert "search_ingredients" in desc[name], name
    assert "canonical_name" in desc["search_ingredients"]
