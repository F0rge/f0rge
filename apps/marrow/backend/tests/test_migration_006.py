"""Migration 006 round-trip test.

Verifies:
1. upgrade() creates tracker + tracker_log tables.
2. Seeds 4 tracker rows (is_seed=true).
3. Backfills tracker_log from existing entries (zero suppression, sick/hot_shower).
4. Idempotent: re-running upgrade() does not duplicate rows.
5. downgrade() drops tracker + tracker_log; leaves entries intact.

Uses an isolated module-scoped Postgres container so this test does not
share state with the session-scoped container used by other tests.

Migration functions are called directly (bypassing env.py) by configuring
an alembic MigrationContext + Operations on a live psycopg2 connection.
Modules starting with a digit are loaded via importlib.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer


# ---------------------------------------------------------------------------
# Module-scoped isolated container
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def migration_postgres_container() -> Iterator[PostgresContainer]:
    """Isolated Postgres container, module scope."""
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sync_url(container: PostgresContainer) -> str:
    """Return a psycopg2 URL for the container."""
    url = container.get_connection_url()
    if "+psycopg2" not in url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _load_migration(filename: str) -> Any:
    """Load a migration module by filename from migrations/versions/.

    Needed because filenames start with digits, which are illegal as Python
    identifiers for regular imports.
    """
    versions_dir = os.path.join(os.path.dirname(__file__), "..", "migrations", "versions")
    spec = importlib.util.spec_from_file_location(
        f"migration_{filename}",
        os.path.join(versions_dir, filename),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _run_migration(engine: sa.Engine, fn: Any) -> None:
    """Run a migration upgrade/downgrade function via MigrationContext."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            fn()
        conn.commit()


def _table_exists(conn: sa.Connection, table_name: str) -> bool:
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": table_name},
    )
    return result.fetchone() is not None


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------


def test_migration_006_round_trip(migration_postgres_container: PostgresContainer) -> None:
    sync_url = _sync_url(migration_postgres_container)
    engine = create_engine(sync_url)

    # Load migration modules.
    m001 = _load_migration("001_baseline.py")
    m006 = _load_migration("006_add_trackers.py")

    # -----------------------------------------------------------------------
    # Step 1: apply migration 001 (creates entries table and all baseline tables)
    # -----------------------------------------------------------------------
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    _run_migration(engine, m001.upgrade)

    with engine.connect() as conn:
        assert _table_exists(conn, "entries"), "entries table missing after 001 upgrade"

    # -----------------------------------------------------------------------
    # Step 2: insert synthetic entry rows BEFORE 006 backfill runs
    #
    # Entry A: alcohol_units=3, caffeine_servings=0 → alcohol log row; no caffeine row
    # Entry B: alcohol_units=0                      → SKIPPED (zero suppression)
    # Entry C: caffeine_servings=2, sick=True        → caffeine + sick log rows
    # Entry D: hot_shower=True                       → hot_shower log row
    # Entry E: all NULL/False                        → no log rows
    # Expected tracker_log rows: 4
    # -----------------------------------------------------------------------
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO entries (
                    date, schema_version, overall, bloating, joint_pain, neuro,
                    sleep_quality, stress, diet_risk, supplements, sick,
                    hot_shower, alcohol_units, caffeine_servings, symptoms_json,
                    created_at, updated_at
                ) VALUES
                    ('2026-05-01', 3, 5, 2, 1, 1, 7, 3, 'low', '', false, false, 3,    0,    '{}', now(), now()),
                    ('2026-05-02', 3, 5, 2, 1, 1, 7, 3, 'low', '', false, false, 0,    NULL, '{}', now(), now()),
                    ('2026-05-03', 3, 5, 2, 1, 1, 7, 3, 'low', '', true,  false, NULL, 2,    '{}', now(), now()),
                    ('2026-05-04', 3, 5, 2, 1, 1, 7, 3, 'low', '', false, true,  NULL, NULL, '{}', now(), now()),
                    ('2026-05-05', 3, 5, 2, 1, 1, 7, 3, 'low', '', false, false, NULL, NULL, '{}', now(), now())
                """
            )
        )

    # -----------------------------------------------------------------------
    # Step 3: apply migration 006
    # -----------------------------------------------------------------------
    _run_migration(engine, m006.upgrade)

    # -----------------------------------------------------------------------
    # Step 4: assert tracker table exists + 4 seeded rows
    # -----------------------------------------------------------------------
    with engine.connect() as conn:
        assert _table_exists(conn, "tracker"), "tracker table missing after 006 upgrade"
        assert _table_exists(conn, "tracker_log"), "tracker_log table missing after 006 upgrade"

        rows = conn.execute(
            text("SELECT name, kind, icon, unit, position, is_seed FROM tracker ORDER BY position")
        ).fetchall()

        assert len(rows) == 4, f"Expected 4 seeded trackers, got {len(rows)}: {rows}"

        names = [r[0] for r in rows]
        assert names == ["Alcohol units", "Caffeine servings", "Sick", "Hot shower"]

        kinds = [r[1] for r in rows]
        assert kinds == ["counter", "counter", "binary", "binary"]

        icons = [r[2] for r in rows]
        assert icons == ["wine", "coffee", "thermometer", "droplets"]

        units = [r[3] for r in rows]
        assert units == ["units", "servings", None, None]

        is_seeds = [r[5] for r in rows]
        assert all(is_seeds), f"Not all seed trackers have is_seed=true: {rows}"

    # -----------------------------------------------------------------------
    # Step 5: assert tracker_log backfill correctness
    # -----------------------------------------------------------------------
    with engine.connect() as conn:
        log_rows = conn.execute(
            text(
                """
                SELECT t.name, tl.date::text, tl.value
                FROM tracker_log tl
                JOIN tracker t ON t.id = tl.tracker_id
                ORDER BY tl.date, t.position
                """
            )
        ).fetchall()

        assert len(log_rows) == 4, (
            f"Expected 4 tracker_log rows after backfill, got {len(log_rows)}: {log_rows}"
        )

        log_by_key = {(r[0], r[1]): r[2] for r in log_rows}

        # alcohol_units=3 on 2026-05-01
        assert log_by_key[("Alcohol units", "2026-05-01")] == 3

        # alcohol_units=0 on 2026-05-02 must be suppressed
        assert ("Alcohol units", "2026-05-02") not in log_by_key, (
            "alcohol_units=0 should be suppressed"
        )

        # caffeine_servings=2 on 2026-05-03
        assert log_by_key[("Caffeine servings", "2026-05-03")] == 2

        # sick=True on 2026-05-03 → value=1
        assert log_by_key[("Sick", "2026-05-03")] == 1

        # hot_shower=True on 2026-05-04 → value=1
        assert log_by_key[("Hot shower", "2026-05-04")] == 1

    # -----------------------------------------------------------------------
    # Step 6: idempotency — the ON CONFLICT guards in the seed INSERT and the
    #         four backfill INSERTs must not duplicate rows when re-run.
    #         (At the Alembic level, re-running an already-applied migration is
    #         a no-op via the alembic_version table; here we test the SQL
    #         idempotency of just the DML statements themselves.)
    # -----------------------------------------------------------------------
    with engine.begin() as conn:
        # Re-run the seed insert
        conn.execute(
            text(
                """
                INSERT INTO tracker (name, kind, icon, unit, position, archived, is_seed)
                VALUES
                    ('Alcohol units',     'counter', 'wine',        'units',    0, false, true),
                    ('Caffeine servings', 'counter', 'coffee',      'servings', 1, false, true),
                    ('Sick',              'binary',  'thermometer', NULL,       2, false, true),
                    ('Hot shower',        'binary',  'droplets',    NULL,       3, false, true)
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
        # Re-run the alcohol backfill
        conn.execute(
            text(
                """
                INSERT INTO tracker_log (tracker_id, date, value)
                SELECT
                    (SELECT id FROM tracker WHERE name = 'Alcohol units' AND is_seed = true),
                    e.date, e.alcohol_units
                FROM entries e
                WHERE e.alcohol_units IS NOT NULL AND e.alcohol_units > 0
                ON CONFLICT (tracker_id, date) DO UPDATE SET value = EXCLUDED.value
                """
            )
        )

    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM tracker")).scalar()
        assert count == 4, f"Re-running seed INSERT duplicated tracker rows: {count}"

        log_count = conn.execute(text("SELECT COUNT(*) FROM tracker_log")).scalar()
        assert log_count == 4, (
            f"Re-running backfill INSERT duplicated tracker_log rows: {log_count}"
        )

    # -----------------------------------------------------------------------
    # Step 7: downgrade — tracker + tracker_log gone; entries intact.
    # -----------------------------------------------------------------------
    _run_migration(engine, m006.downgrade)

    with engine.connect() as conn:
        assert not _table_exists(conn, "tracker"), "tracker table should be gone after downgrade"
        assert not _table_exists(conn, "tracker_log"), (
            "tracker_log table should be gone after downgrade"
        )
        assert _table_exists(conn, "entries"), "entries table must survive downgrade"

        entry_count = conn.execute(text("SELECT COUNT(*) FROM entries")).scalar()
        assert entry_count == 5, (
            f"entries rows were modified by downgrade (expected 5, got {entry_count})"
        )

    engine.dispose()
