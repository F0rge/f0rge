"""Regression test for migration 033's created_at backfill under FORCE RLS.

Prod (f0rge-db) runs ``alembic upgrade`` as ``schema_admin`` — a NOSUPERUSER,
NOBYPASSRLS role — and ``tracker_log`` uses FORCE ROW LEVEL SECURITY with the
``tenant_isolation`` policy (USING ``user_id = app.user_id``). The original
migration 033 tried to backfill ``created_at`` via ``DEFAULT updated_at`` DDL,
which Postgres rejects outright (a column DEFAULT can't reference another
column). The fix does a real UPDATE, scoped per-tenant via
``set_config('app.user_id', ...)`` — same pattern as migration 031.

This test proves why the per-tenant scoping matters: a naive UPDATE with no
WHERE on user_id, run under RLS as a non-owner role, doesn't raise — the
USING clause simply hides every row outside the current tenant, so it
silently backfills only the current tenant and leaves the rest NULL.

The normal suite can't see this: conftest connects as the postgres SUPERUSER,
which bypasses RLS. This test reproduces the prod condition with a
NOSUPERUSER/NOBYPASSRLS ``rls_probe`` role under ``SET ROLE``.
"""

from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings

_LEO_TRACKER_ID = 9001
_OTHER_TRACKER_ID = 9002
_LOG_DATE = datetime.date(2026, 1, 1)


async def test_migration_033_created_at_backfill_is_rls_safe(async_engine: AsyncEngine) -> None:
    leo_id = uuid.UUID(settings.default_storage_user_id)
    other_id = uuid.uuid4()
    leo_updated_at = datetime.datetime(2026, 1, 1, 10, 0, 0)
    other_updated_at = datetime.datetime(2026, 1, 2, 11, 0, 0)

    async with async_engine.connect() as conn:
        trans = await conn.begin()
        try:
            # --- superuser setup (RLS bypassed) ---
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO users (id, email, password_hash, avatar_default_index, created_at)
                    VALUES (:id, :email, 'x', 0, now())
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {"id": other_id, "email": f"probe-{other_id}@test.local"},
            )

            # Simulate migration step 1: created_at exists, nullable, no
            # column-referencing default (the ORM schema already has it
            # NOT NULL, so relax it to reproduce the pre-backfill state).
            await conn.execute(
                sa.text("ALTER TABLE tracker_log ALTER COLUMN created_at DROP NOT NULL")
            )

            for uid, tracker_id, updated_at in (
                (leo_id, _LEO_TRACKER_ID, leo_updated_at),
                (other_id, _OTHER_TRACKER_ID, other_updated_at),
            ):
                await conn.execute(
                    sa.text(
                        """
                        INSERT INTO tracker
                            (id, user_id, name, kind, position, archived, is_seed, created_at)
                        VALUES (:tid, :uid, 'probe', 'counter', 0, false, false, now())
                        """
                    ),
                    {"tid": tracker_id, "uid": uid},
                )
                await conn.execute(
                    sa.text(
                        """
                        INSERT INTO tracker_log
                            (user_id, tracker_id, date, value, updated_at, created_at)
                        VALUES (:uid, :tid, :date, 1, :updated_at, NULL)
                        """
                    ),
                    {"uid": uid, "tid": tracker_id, "date": _LOG_DATE, "updated_at": updated_at},
                )

            await conn.execute(sa.text("CREATE ROLE rls_probe NOSUPERUSER NOBYPASSRLS"))
            await conn.execute(sa.text("GRANT SELECT, UPDATE ON tracker_log TO rls_probe"))
            await conn.execute(sa.text("GRANT SELECT ON users TO rls_probe"))

            # --- negative (documents the bug): a naive cross-tenant UPDATE with
            # no WHERE on user_id, scoped by RLS to Leo only, silently leaves
            # the other tenant's row NULL — RLS hides it, it doesn't raise. ---
            await conn.execute(sa.text("SET ROLE rls_probe"))
            await conn.execute(
                sa.text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(leo_id)}
            )
            await conn.execute(sa.text("UPDATE tracker_log SET created_at = updated_at"))
            await conn.execute(sa.text("RESET ROLE"))

            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT user_id, created_at FROM tracker_log WHERE tracker_id IN (:t1, :t2)"
                    ),
                    {"t1": _LEO_TRACKER_ID, "t2": _OTHER_TRACKER_ID},
                )
            ).all()
            by_user = {r.user_id: r.created_at for r in rows}
            assert by_user[leo_id] is not None
            assert by_user[other_id] is None

            # --- positive (proves the fix): the per-tenant loop backfills both. ---
            await conn.execute(sa.text("SET ROLE rls_probe"))
            for uid in (leo_id, other_id):
                await conn.execute(
                    sa.text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(uid)}
                )
                await conn.execute(
                    sa.text(
                        """
                        UPDATE tracker_log
                        SET created_at = updated_at
                        WHERE user_id = CAST(:uid AS uuid) AND created_at IS NULL
                        """
                    ),
                    {"uid": str(uid)},
                )
            await conn.execute(sa.text("RESET ROLE"))

            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT user_id, created_at, updated_at FROM tracker_log "
                        "WHERE tracker_id IN (:t1, :t2)"
                    ),
                    {"t1": _LEO_TRACKER_ID, "t2": _OTHER_TRACKER_ID},
                )
            ).all()
            by_user = {r.user_id: (r.created_at, r.updated_at) for r in rows}
            assert by_user[leo_id][0] == by_user[leo_id][1]
            assert by_user[other_id][0] == by_user[other_id][1]
        finally:
            await trans.rollback()
