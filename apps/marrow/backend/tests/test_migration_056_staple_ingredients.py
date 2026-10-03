"""Migration 056: backfill muesli/flour/bread/pasta/cocoa into existing users' catalogues.

Runs the migration's data step as a NOSUPERUSER / NOBYPASSRLS table owner (the prod
``schema_admin`` condition, see test_migration_031_rls_safe.py) with the real
``migration_bypass`` helper. The normal suite connects as a superuser and cannot see RLS bugs.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from f0rge_db.rls import migration_bypass

_BACKEND = Path(__file__).resolve().parents[1]
_MIGRATION = _BACKEND / "migrations" / "versions" / "056_backfill_staple_ingredients.py"
_DATA = _BACKEND / "data" / "curated_ingredients_2026_09.json"
_NEW = {"muesli", "flour", "bread", "pasta", "cocoa"}


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_056", _MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_upgrade_data_step(sync_conn: sa.Connection) -> None:
    module = _load_migration()
    with migration_bypass(sync_conn, module._RLS_TABLES):
        module.backfill_staple_ingredients(sync_conn)


async def _seed_users(conn: AsyncConnection, *user_ids: uuid.UUID) -> None:
    for uid in user_ids:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, avatar_default_index, created_at) "
                "VALUES (:id, :email, 'x', 0, now()) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": uid, "email": f"m056-{uid}@test.local"},
        )


async def _ingredient(conn: AsyncConnection, uid: uuid.UUID, name: str):
    return (
        await conn.execute(
            sa.text(
                "SELECT canonical_name, archived, contains_gluten, histamine_score, source "
                "FROM dietary_ingredients WHERE user_id = :u AND canonical_name = :n"
            ),
            {"u": uid, "n": name},
        )
    ).one_or_none()


async def _alias_target(conn: AsyncConnection, uid: uuid.UUID, alias: str):
    return (
        await conn.execute(
            sa.text("SELECT canonical_name FROM ingredient_aliases WHERE user_id=:u AND alias=:a"),
            {"u": uid, "a": alias},
        )
    ).scalar_one_or_none()


def test_seed_file_is_consistent() -> None:
    payload = json.loads(_DATA.read_text(encoding="utf-8"))
    names = {i["canonical_name"] for i in payload["ingredients"]}
    assert names == _NEW
    for item in payload["ingredients"]:
        assert item["histamine_score"] in (0, 1, 2, 3)
        for axis in ("oligos", "fructose", "polyols", "lactose"):
            assert item[f"fodmap_{axis}"] in ("low", "moderate", "high")
    assert {a["canonical_name"] for a in payload["aliases"]} <= names
    alias_names = [a["alias"] for a in payload["aliases"]]
    assert len(alias_names) == len(set(alias_names))
    assert not (set(alias_names) & names)
    # Misleading aliases deliberately excluded.
    assert "cereal" not in alias_names and "oatmeal" not in alias_names


async def test_backfill_adds_missing_keeps_user_rows_and_is_idempotent(
    superuser_engine: AsyncEngine,
) -> None:
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with superuser_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _seed_users(conn, user_a, user_b)
            # User A already customised: archived "bread" with different flags, and their own
            # "granola" alias pointing at another canonical.
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO dietary_ingredients
                        (user_id, canonical_name, histamine_score, contains_gluten,
                         contains_dairy, archived, source, created_at, updated_at)
                    VALUES
                        (:u, 'bread', 3, false, false, true, 'user', now(), now()),
                        (:u, 'my cereal', 0, false, false, false, 'user', now(), now())
                    """
                ),
                {"u": user_a},
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO ingredient_aliases (user_id, alias, canonical_name, language, "
                    "created_at) VALUES (:u, 'granola', 'my cereal', 'en', now())"
                ),
                {"u": user_a},
            )
            # Prod condition: NOSUPERUSER/NOBYPASSRLS owner of the catalogue tables.
            await conn.execute(sa.text("CREATE ROLE rls_probe_056 NOSUPERUSER NOBYPASSRLS"))
            for table in ("dietary_ingredients", "ingredient_aliases"):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO rls_probe_056"))
            await conn.execute(sa.text("GRANT USAGE ON SCHEMA public TO rls_probe_056"))
            await conn.execute(sa.text("GRANT SELECT ON users TO rls_probe_056"))
            await conn.execute(
                sa.text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rls_probe_056")
            )
            await conn.execute(sa.text("SET ROLE rls_probe_056"))

            await conn.run_sync(_run_upgrade_data_step)
            await conn.run_sync(_run_upgrade_data_step)  # idempotent re-run
            await conn.execute(sa.text("RESET ROLE"))  # verify as superuser (RLS off)

            for uid in (user_a, user_b):
                for name in _NEW - {"bread"} if uid == user_a else _NEW:
                    row = await _ingredient(conn, uid, name)
                    assert row is not None, (uid, name)
                    assert row.archived is False
                    assert row.source == "mcp-catalogue-gap-fill-2026-09"

            new_b = {n: await _ingredient(conn, user_b, n) for n in _NEW}
            assert new_b["bread"].contains_gluten is True
            assert new_b["muesli"].contains_gluten is True
            assert new_b["cocoa"].contains_gluten is False
            assert new_b["cocoa"].histamine_score == 2

            # User A's own rows / aliases untouched.
            bread_a = await _ingredient(conn, user_a, "bread")
            assert (bread_a.archived, bread_a.contains_gluten, bread_a.histamine_score) == (
                True,
                False,
                3,
            )
            assert bread_a.source == "user"
            assert await _alias_target(conn, user_a, "granola") == "my cereal"
            assert await _alias_target(conn, user_b, "granola") == "muesli"

            # No duplicates after two runs.
            counts = (
                await conn.execute(
                    sa.text(
                        "SELECT user_id, canonical_name, count(*) FROM dietary_ingredients "
                        "WHERE user_id IN (:a, :b) GROUP BY 1, 2 HAVING count(*) > 1"
                    ),
                    {"a": user_a, "b": user_b},
                )
            ).all()
            assert counts == []
            assert await _alias_target(conn, user_b, "spaghetti") == "pasta"
            assert await _alias_target(conn, user_a, "spaghetti") == "pasta"
        finally:
            await trans.rollback()
            await conn.execute(sa.text("RESET ALL"))
