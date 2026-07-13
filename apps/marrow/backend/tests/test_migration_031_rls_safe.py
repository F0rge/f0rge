"""Regression test for cross-tenant Alembic writes under FORCE RLS.

Prod (f0rge-db) runs ``alembic upgrade`` as ``schema_admin`` — a NOSUPERUSER,
NOBYPASSRLS role — and user-owned tables use FORCE ROW LEVEL SECURITY with the
``tenant_isolation`` policy. Cross-tenant statements without a bypass raise
InsufficientPrivilege (migration 031's original bug) or fail silently (0 rows).

The standard fix is a transient ``migration_bypass`` policy from ``f0rge_db.rls``
(see backend.mdc § Alembic migrations under FORCE RLS). This test exercises that
pattern against ``symptom_catalog`` using the same bulk INSERT shape migration 031
needed.

The normal suite can't see this bug: conftest connects as the postgres SUPERUSER,
which bypasses RLS. This test reproduces the prod condition by creating a
NOSUPERUSER / NOBYPASSRLS role that owns the table (like ``schema_admin``) and
running under ``SET ROLE``.

The negative (raising) case and the positive case run on separate connections:
the raising INSERT aborts its transaction, and a top-level ROLLBACK is the clean
way to recover (a SAVEPOINT rollback does not reliably clear the aborted state
under asyncpg). The negative rollback also undoes its transactional ``CREATE
ROLE``, so the positive half can recreate ``rls_probe``.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.config import settings
from f0rge_db.rls import install_migration_bypass, remove_migration_bypass


async def _seed_prod_condition(
    conn: AsyncConnection, leo_id: uuid.UUID, other_id: uuid.UUID
) -> None:
    """Two users (Leo + a random non-ref), a joint_pain seed row each, and a
    NOSUPERUSER/NOBYPASSRLS ``rls_probe`` role — all as the superuser (RLS off)."""
    for uid, email in ((leo_id, f"leo-probe-{leo_id}"), (other_id, f"probe-{other_id}")):
        await conn.execute(
            sa.text(
                """
                INSERT INTO users
                    (id, email, password_hash, avatar_default_index, created_at)
                VALUES (:id, :email, 'x', 0, now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": uid, "email": f"{email}@test.local"},
        )
        # A seed joint_pain row for each (mirrors DEFAULT_SYMPTOMS from mig 009).
        await conn.execute(
            sa.text(
                """
                INSERT INTO symptom_catalog
                    (user_id, key, label, archived, sort_order, created_at, updated_at)
                VALUES (:u, 'joint_pain', 'Joint Pain', false, 0, now(), now())
                ON CONFLICT ON CONSTRAINT uq_symptom_catalog_user_id_key DO NOTHING
                """
            ),
            {"u": uid},
        )
    await conn.execute(sa.text("CREATE ROLE rls_probe NOSUPERUSER NOBYPASSRLS"))
    await conn.execute(sa.text("ALTER TABLE symptom_catalog OWNER TO rls_probe"))
    await conn.execute(sa.text("ALTER TABLE entries OWNER TO rls_probe"))
    await conn.execute(
        sa.text("GRANT SELECT, INSERT, UPDATE ON symptom_catalog, entries TO rls_probe")
    )
    await conn.execute(sa.text("GRANT SELECT ON users TO rls_probe"))
    await conn.execute(sa.text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rls_probe"))


async def test_migration_031_seed_is_rls_safe(superuser_engine: AsyncEngine) -> None:
    leo_id = uuid.UUID(settings.default_storage_user_id)
    other_id = uuid.uuid4()

    # --- negative (documents the bug): cross-tenant INSERT without bypass RAISES. ---
    async with superuser_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _seed_prod_condition(conn, leo_id, other_id)
            await conn.execute(sa.text("SET ROLE rls_probe"))
            await conn.execute(
                sa.text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(leo_id)},
            )
            with pytest.raises(ProgrammingError):
                await conn.execute(
                    sa.text(
                        """
                        INSERT INTO symptom_catalog
                            (user_id, key, label, archived, sort_order, created_at, updated_at)
                        SELECT id, 'neuro_symptoms', 'Neuro symptoms', true, 99, now(), now()
                        FROM users
                        """
                    )
                )
        finally:
            # Top-level ROLLBACK clears the aborted txn + undoes the CREATE ROLE.
            await trans.rollback()
            await conn.execute(sa.text("RESET ALL"))

    # --- positive (proves the fix): transient migration_bypass succeeds under RLS. ---
    async with superuser_engine.connect() as conn:
        trans = await conn.begin()
        try:
            await _seed_prod_condition(conn, leo_id, other_id)
            # Migration 029 bulk-seeds Leo's catalog rows archived; 031's INSERT
            # no-ops on conflict, so the post-insert un-archive is required.
            await conn.execute(
                sa.text(
                    """
                    UPDATE symptom_catalog SET archived = true
                    WHERE user_id = :u AND key = 'joint_pain'
                    """
                ),
                {"u": leo_id},
            )
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO symptom_catalog
                        (user_id, key, label, archived, sort_order, created_at, updated_at)
                    VALUES (:u, 'neuro_symptoms', 'Neuro symptoms', true, 99, now(), now())
                    ON CONFLICT ON CONSTRAINT uq_symptom_catalog_user_id_key DO NOTHING
                    """
                ),
                {"u": leo_id},
            )
            await conn.execute(sa.text("SET ROLE rls_probe"))

            await conn.run_sync(
                lambda sync_conn: install_migration_bypass(sync_conn, ["symptom_catalog"])
            )
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO symptom_catalog (
                        user_id, key, label, archived, sort_order, created_at, updated_at
                    )
                    SELECT
                        u.id,
                        'neuro_symptoms',
                        'Neuro symptoms',
                        CASE WHEN u.id = CAST(:leo_id AS uuid) THEN false ELSE true END,
                        COALESCE(
                            (SELECT MAX(sort_order) FROM symptom_catalog sc
                             WHERE sc.user_id = u.id),
                            -1
                        ) + 1,
                        now(),
                        now()
                    FROM users u
                    ON CONFLICT ON CONSTRAINT uq_symptom_catalog_user_id_key DO NOTHING
                    """
                ),
                {"leo_id": str(leo_id)},
            )
            await conn.execute(
                sa.text(
                    """
                    UPDATE symptom_catalog
                    SET archived = false, updated_at = now()
                    WHERE user_id = CAST(:leo_id AS uuid)
                      AND key = ANY(:keys)
                    """
                ),
                {"leo_id": str(leo_id), "keys": ["joint_pain", "neuro_symptoms"]},
            )
            await conn.run_sync(
                lambda sync_conn: remove_migration_bypass(sync_conn, ["symptom_catalog"])
            )
            await conn.execute(sa.text("RESET ROLE"))

            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT user_id, key, archived FROM symptom_catalog "
                        "WHERE key IN ('joint_pain', 'neuro_symptoms')"
                    )
                )
            ).all()
            by_user_key = {(r.user_id, r.key): r.archived for r in rows}
            assert by_user_key[(other_id, "neuro_symptoms")] is True
            assert by_user_key[(leo_id, "joint_pain")] is False
            assert by_user_key[(leo_id, "neuro_symptoms")] is False
        finally:
            await trans.rollback()
            await conn.execute(sa.text("RESET ALL"))
