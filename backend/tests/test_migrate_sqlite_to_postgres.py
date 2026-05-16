"""Integration test for migrate_sqlite_to_postgres.

Spins up a real Postgres via testcontainers, creates a tiny SQLite fixture,
runs the migration, and asserts correctness.

Skipped automatically if Docker is not running.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------


def _docker_running() -> bool:
    import subprocess  # noqa: PLC0415

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sqlite_db_path() -> Iterator[str]:
    """Create a minimal SQLite fixture with known data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # We build the tables manually to mirror what the ORM would create.
    # This avoids needing alembic on the source side.

    cur.executescript(
        """
        CREATE TABLE entries (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            schema_version INTEGER NOT NULL DEFAULT 3,
            entry_time TEXT,
            period_of_day TEXT,
            overall INTEGER NOT NULL,
            bloating INTEGER NOT NULL,
            stool_normal INTEGER,
            stool_type TEXT,
            stool_status TEXT,
            bristol_type INTEGER,
            joint_pain INTEGER NOT NULL,
            neuro INTEGER NOT NULL,
            sleep_quality INTEGER NOT NULL,
            stress INTEGER NOT NULL,
            diet_risk TEXT NOT NULL,
            supplements TEXT NOT NULL,
            sick INTEGER NOT NULL,
            hot_shower INTEGER NOT NULL DEFAULT 0,
            alcohol_units INTEGER,
            caffeine_servings INTEGER,
            symptoms_json TEXT NOT NULL DEFAULT '{}',
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE photos (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER NOT NULL REFERENCES entries(id),
            filename TEXT NOT NULL,
            label TEXT,
            original_filename TEXT,
            meal_time TEXT,
            created_at TEXT
        );

        CREATE TABLE photo_analyses (
            id INTEGER PRIMARY KEY,
            photo_id INTEGER NOT NULL UNIQUE REFERENCES photos(id),
            status TEXT NOT NULL DEFAULT 'pending',
            dish_name TEXT,
            cuisine TEXT,
            dish_confidence REAL,
            raw_response TEXT,
            error_message TEXT,
            model_id TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE photo_ingredients (
            id INTEGER PRIMARY KEY,
            analysis_id INTEGER NOT NULL REFERENCES photo_analyses(id),
            name TEXT NOT NULL,
            canonical_name TEXT,
            visible INTEGER DEFAULT 1,
            confidence REAL NOT NULL,
            user_edited INTEGER DEFAULT 0,
            histamine_score INTEGER,
            fodmap_oligos TEXT,
            fodmap_fructose TEXT,
            fodmap_polyols TEXT,
            fodmap_lactose TEXT,
            contains_gluten INTEGER,
            contains_dairy INTEGER,
            created_at TEXT
        );

        CREATE TABLE dietary_ingredients (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            category TEXT,
            histamine_score INTEGER,
            fodmap_oligos TEXT,
            fodmap_fructose TEXT,
            fodmap_polyols TEXT,
            fodmap_lactose TEXT,
            contains_gluten INTEGER DEFAULT 0,
            contains_dairy INTEGER DEFAULT 0,
            source TEXT,
            source_version TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE ingredient_aliases (
            id INTEGER PRIMARY KEY,
            alias TEXT NOT NULL,
            canonical_name TEXT NOT NULL REFERENCES dietary_ingredients(canonical_name),
            language TEXT DEFAULT 'en'
        );

        CREATE TABLE auth_sessions (
            id INTEGER PRIMARY KEY,
            token TEXT NOT NULL UNIQUE,
            created_at TEXT,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE supplement_catalog (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            first_used_at TEXT,
            last_used_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE symptom_catalog (
            id INTEGER PRIMARY KEY,
            key TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            first_used_at TEXT,
            last_used_at TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE health_metrics (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL UNIQUE,
            hrv_mean REAL,
            hrv_std REAL,
            resting_hr REAL,
            sleep_hours REAL,
            sleep_deep_min REAL,
            sleep_rem_min REAL,
            sleep_core_min REAL,
            sleep_awake_min REAL,
            sleep_deep_pct REAL,
            sleep_rem_pct REAL,
            sleep_efficiency REAL,
            sleep_start TEXT,
            sleep_end TEXT,
            steps INTEGER,
            active_minutes REAL,
            spo2 REAL,
            wrist_temp_deviation REAL,
            source TEXT NOT NULL DEFAULT 'health_auto_export',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE weather_readings (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL,
            temperature_c REAL NOT NULL,
            humidity_pct REAL NOT NULL,
            pressure_hpa REAL NOT NULL,
            weather_main TEXT,
            created_at TEXT
        );

        CREATE TABLE labs (
            id INTEGER PRIMARY KEY,
            lab_date TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            lab_location TEXT,
            source_path TEXT,
            source_kind TEXT NOT NULL,
            attachment_path TEXT,
            raw_text TEXT,
            extraction_model TEXT,
            extraction_confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'confirmed',
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE lab_marker_catalog (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            common_units TEXT NOT NULL DEFAULT '[]',
            description TEXT,
            created_at TEXT
        );

        CREATE TABLE lab_marker_aliases (
            id INTEGER PRIMARY KEY,
            catalog_id INTEGER NOT NULL REFERENCES lab_marker_catalog(id),
            alias TEXT NOT NULL UNIQUE,
            language TEXT
        );

        CREATE TABLE lab_markers (
            id INTEGER PRIMARY KEY,
            lab_id INTEGER NOT NULL REFERENCES labs(id),
            catalog_id INTEGER NOT NULL REFERENCES lab_marker_catalog(id),
            canonical_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            value REAL,
            value_text TEXT,
            unit TEXT,
            ref_low REAL,
            ref_high REAL,
            ref_text TEXT,
            flag TEXT NOT NULL
        );

        CREATE TABLE treatments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            dose TEXT,
            notes TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )

    now = datetime.datetime.utcnow().isoformat()
    symptoms = json.dumps({"headache": 2, "fatigue": 1})

    # entry with non-trivial JSON
    cur.execute(
        "INSERT INTO entries VALUES (1, '2024-01-15', 3, ?, 'morning', 3, 2, NULL, NULL, "
        "'normal', 4, 1, 2, 7, 3, 'low', '', 0, 0, 0, 1, ?, 'test', ?, ?)",
        (now, symptoms, now, now),
    )

    # photo -> photo_analysis -> photo_ingredient
    cur.execute(
        "INSERT INTO photos VALUES (1, 1, 'test.jpg', 'lunch', 'test.jpg', NULL, ?)", (now,)
    )
    cur.execute(
        "INSERT INTO photo_analyses VALUES (1, 1, 'complete', 'salad', 'french', 0.9, "
        "NULL, NULL, 'model-v1', ?, ?)",
        (now, now),
    )
    cur.execute(
        "INSERT INTO photo_ingredients VALUES (1, 1, 'lettuce', 'lettuce', 1, 0.95, 0, "
        "0, NULL, NULL, NULL, NULL, 0, 0, ?)",
        (now,),
    )
    cur.execute(
        "INSERT INTO photo_ingredients VALUES (2, 1, 'tomato', 'tomato', 1, 0.88, 0, "
        "1, 'low', 'low', NULL, NULL, 0, 0, ?)",
        (now,),
    )

    # dietary ingredient + alias
    cur.execute(
        "INSERT INTO dietary_ingredients VALUES (1, 'lettuce', 'leafy green', 0, "
        "NULL, NULL, NULL, NULL, 0, 0, 'sighi', '2024-01', ?, ?)",
        (now, now),
    )
    cur.execute(
        "INSERT INTO ingredient_aliases VALUES (1, 'green lettuce', 'lettuce', 'en')"
    )

    # lab_marker_catalog with JSON list
    cur.execute(
        "INSERT INTO lab_marker_catalog VALUES (1, 'ferritin', 'Ferritin', "
        "?, 'Iron storage protein', ?)",
        (json.dumps(["ng/mL", "pmol/L"]), now),
    )

    # auth session — one valid, one expired
    future = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat()
    past = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
    cur.execute(
        "INSERT INTO auth_sessions VALUES (1, 'valid-token', ?, ?)", (now, future)
    )
    cur.execute(
        "INSERT INTO auth_sessions VALUES (2, 'expired-token', ?, ?)", (now, past)
    )

    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def migration_postgres_container():  # type: ignore[no-untyped-def]
    """Dedicated Postgres container for the migration test — isolated from the shared one."""
    from testcontainers.postgres import PostgresContainer  # noqa: PLC0415

    import app.models  # noqa: F401

    from app.database import Base  # noqa: PLC0415

    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()

    # Create schema via Base.metadata (sync engine).
    raw_url = container.get_connection_url()
    if "+psycopg2" not in raw_url:
        sync_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        sync_url = raw_url

    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    try:
        yield container
    finally:
        container.stop()


@pytest.mark.skipif(not _docker_running(), reason="Docker not running")
def test_migrate_sqlite_to_postgres(
    sqlite_db_path: str, migration_postgres_container
) -> None:  # type: ignore[no-untyped-def]
    """Full round-trip: SQLite fixture -> Postgres -> verify."""
    import app.models  # noqa: F401

    from scripts.migrate_sqlite_to_postgres import run_migration

    # Build psycopg2 URL from the testcontainers-provided URL.
    raw_url = migration_postgres_container.get_connection_url()
    if "+psycopg2" not in raw_url:
        pg_url = raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    else:
        pg_url = raw_url
    sqlite_url = f"sqlite:///{sqlite_db_path}"

    # 1. Run migration — expect success.
    exit_code = run_migration(
        sqlite_url=sqlite_url,
        postgres_url=pg_url,
        prune_expired_sessions=True,
        dry_run=False,
    )
    assert exit_code == 0, f"Migration returned exit code {exit_code}, expected 0"

    # 2. Connect to Postgres and verify.
    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Row counts
        assert session.execute(text("SELECT COUNT(*) FROM entries")).scalar() == 1
        assert session.execute(text("SELECT COUNT(*) FROM photos")).scalar() == 1
        assert session.execute(text("SELECT COUNT(*) FROM photo_analyses")).scalar() == 1
        assert session.execute(text("SELECT COUNT(*) FROM photo_ingredients")).scalar() == 2
        assert session.execute(text("SELECT COUNT(*) FROM dietary_ingredients")).scalar() == 1
        assert session.execute(text("SELECT COUNT(*) FROM ingredient_aliases")).scalar() == 1
        assert session.execute(text("SELECT COUNT(*) FROM lab_marker_catalog")).scalar() == 1

        # Pruned sessions: only the valid one should remain.
        assert session.execute(text("SELECT COUNT(*) FROM auth_sessions")).scalar() == 1
        token = session.execute(text("SELECT token FROM auth_sessions")).scalar()
        assert token == "valid-token", f"Expected 'valid-token', got {token!r}"

        # JSON deep-equal: symptoms_json
        from app.models.entry import Entry  # noqa: PLC0415

        entry = session.get(Entry, 1)
        assert entry is not None
        symptoms = entry.symptoms_json
        if isinstance(symptoms, str):
            symptoms = json.loads(symptoms)
        assert symptoms == {"headache": 2, "fatigue": 1}, f"symptoms_json mismatch: {symptoms!r}"

        # JSON deep-equal: common_units
        from app.models.lab_marker_catalog import LabMarkerCatalog  # noqa: PLC0415

        cat = session.get(LabMarkerCatalog, 1)
        assert cat is not None
        units = cat.common_units
        if isinstance(units, str):
            units = json.loads(units)
        assert units == ["ng/mL", "pmol/L"], f"common_units mismatch: {units!r}"

        # FK integrity — no orphans
        orphan_photos = session.execute(
            text(
                "SELECT COUNT(*) FROM photos p "
                "WHERE NOT EXISTS (SELECT 1 FROM entries e WHERE e.id = p.entry_id)"
            )
        ).scalar()
        assert orphan_photos == 0

        orphan_analyses = session.execute(
            text(
                "SELECT COUNT(*) FROM photo_analyses pa "
                "WHERE NOT EXISTS (SELECT 1 FROM photos p WHERE p.id = pa.photo_id)"
            )
        ).scalar()
        assert orphan_analyses == 0

        orphan_ingredients = session.execute(
            text(
                "SELECT COUNT(*) FROM photo_ingredients pi "
                "WHERE NOT EXISTS "
                "(SELECT 1 FROM photo_analyses pa WHERE pa.id = pi.analysis_id)"
            )
        ).scalar()
        assert orphan_ingredients == 0

    finally:
        session.close()
        engine.dispose()

    # 3. Idempotency: second run must refuse (exit 1).
    exit_code2 = run_migration(
        sqlite_url=sqlite_url,
        postgres_url=pg_url,
        prune_expired_sessions=True,
        dry_run=False,
    )
    assert exit_code2 == 1, f"Second run should exit 1 (already migrated), got {exit_code2}"
