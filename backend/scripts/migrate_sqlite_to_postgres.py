"""Migrate live SQLite data to Postgres.

CLI usage:
    python -m scripts.migrate_sqlite_to_postgres \\
        --sqlite /path/to/health.db \\
        --postgres postgresql+psycopg2://health:PASS@host:5432/health \\
        [--no-prune-expired-sessions] \\
        [--dry-run]

Exit codes:
    0 — success
    1 — refused: target Postgres already has data (idempotency guard)
    2 — verification failure
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import random
import sys
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, make_transient, sessionmaker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(url: str) -> Session:
    engine = create_engine(url, echo=False)
    factory = sessionmaker(bind=engine)
    return factory()


def _detach_copy(row: Any) -> Any:
    """Return a transient clone of an ORM row for insertion into a different session."""
    # Capture all column values before expiry on detach.
    # We iterate the mapper's column attrs to get the loaded Python values.
    from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415

    insp = sa_inspect(row)
    state: dict[str, Any] = {}
    for attr in insp.attrs:
        key = attr.key
        # Skip relationship attributes — we don't want lazy loads on a detached instance.
        if key in insp.mapper.relationships.keys():
            continue
        state[key] = getattr(row, key)

    # Clone: new instance, populate columns, mark transient.
    cls = type(row)
    new_row = cls.__new__(cls)
    cls.__init__(new_row)  # type: ignore[misc]
    for k, v in state.items():
        setattr(new_row, k, v)
    make_transient(new_row)
    return new_row


def migrate_table(
    src: Session,
    dst: Session,
    Model: Any,
    *,
    where: Any = None,
    dry_run: bool = False,
) -> int:
    """Copy all rows of *Model* from src to dst. Returns row count transferred."""
    stmt = select(Model)
    if where is not None:
        stmt = stmt.where(where)
    rows = src.scalars(stmt).all()

    if dry_run:
        log.info("  [dry-run] would migrate %d rows from %s", len(rows), Model.__tablename__)
        return len(rows)

    count = 0
    for row in rows:
        new_row = _detach_copy(row)
        dst.merge(new_row)
        count += 1

    dst.commit()
    return count


def reset_sequence(dst: Session, table_name: str, id_col: str = "id") -> None:
    """Reset the Postgres sequence for *table_name.id_col* to MAX(id_col)."""
    dst.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence(:t, :c), "
            f"COALESCE((SELECT MAX({id_col}) FROM {table_name}), 1), "
            f"(SELECT MAX({id_col}) IS NOT NULL FROM {table_name}))"
        ),
        {"t": table_name, "c": id_col},
    )
    dst.commit()


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------


def _fk_orphan_check(dst: Session) -> list[str]:
    """Return a list of error strings for any FK orphans found."""
    checks = [
        ("photos", "entry_id", "entries", "id"),
        ("lab_markers", "lab_id", "labs", "id"),
        ("photo_analyses", "photo_id", "photos", "id"),
        ("photo_ingredients", "analysis_id", "photo_analyses", "id"),
    ]
    errors: list[str] = []
    for child_tbl, fk_col, parent_tbl, parent_col in checks:
        result = dst.execute(
            text(
                f"SELECT COUNT(*) FROM {child_tbl} c "
                f"WHERE NOT EXISTS (SELECT 1 FROM {parent_tbl} p WHERE p.{parent_col} = c.{fk_col})"
            )
        ).scalar()
        if result:
            errors.append(f"FK orphans: {child_tbl}.{fk_col} -> {parent_tbl}: {result} rows")
    return errors


def _json_sample_check(src: Session, dst: Session) -> list[str]:
    """JSON deep-equal check on 10% sample of entries.symptoms_json and lab_marker_catalog.common_units."""
    from app.models.entry import Entry  # noqa: PLC0415
    from app.models.lab_marker_catalog import LabMarkerCatalog  # noqa: PLC0415

    errors: list[str] = []

    # entries.symptoms_json
    all_entry_ids = [r for (r,) in src.execute(text("SELECT id FROM entries")).fetchall()]
    sample_size = max(1, len(all_entry_ids) // 10)
    sample_ids = random.sample(all_entry_ids, min(sample_size, len(all_entry_ids)))
    for eid in sample_ids:
        src_row = src.get(Entry, eid)
        dst_row = dst.get(Entry, eid)
        if src_row is None or dst_row is None:
            errors.append(f"Entry id={eid} missing in src or dst")
            continue
        src_val = src_row.symptoms_json
        dst_val = dst_row.symptoms_json
        # Normalise: sqlite may return string, postgres returns dict
        if isinstance(src_val, str):
            src_val = json.loads(src_val)
        if isinstance(dst_val, str):
            dst_val = json.loads(dst_val)
        if src_val != dst_val:
            errors.append(f"Entry id={eid} symptoms_json mismatch: {src_val!r} != {dst_val!r}")

    # lab_marker_catalog.common_units
    all_cat_ids = [r for (r,) in src.execute(text("SELECT id FROM lab_marker_catalog")).fetchall()]
    cat_sample_size = max(1, len(all_cat_ids) // 10)
    cat_sample_ids = random.sample(all_cat_ids, min(cat_sample_size, len(all_cat_ids)))
    for cid in cat_sample_ids:
        src_row = src.get(LabMarkerCatalog, cid)
        dst_row = dst.get(LabMarkerCatalog, cid)
        if src_row is None or dst_row is None:
            errors.append(f"LabMarkerCatalog id={cid} missing in src or dst")
            continue
        src_val = src_row.common_units
        dst_val = dst_row.common_units
        if isinstance(src_val, str):
            src_val = json.loads(src_val)
        if isinstance(dst_val, str):
            dst_val = json.loads(dst_val)
        if src_val != dst_val:
            errors.append(
                f"LabMarkerCatalog id={cid} common_units mismatch: {src_val!r} != {dst_val!r}"
            )

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_migration(
    sqlite_url: str,
    postgres_url: str,
    prune_expired_sessions: bool = True,
    dry_run: bool = False,
) -> int:
    """Execute the full migration. Returns exit code (0/1/2)."""
    # Import all models so the mapper knows every table.
    import app.models  # noqa: F401, PLC0415
    from app.models.session import AuthSession  # noqa: PLC0415
    from app.models.dietary_ingredient import DietaryIngredient  # noqa: PLC0415
    from app.models.entry import Entry  # noqa: PLC0415
    from app.models.health_metrics import HealthMetric  # noqa: PLC0415
    from app.models.ingredient_alias import IngredientAlias  # noqa: PLC0415
    from app.models.lab import Lab  # noqa: PLC0415
    from app.models.lab_marker import LabMarker  # noqa: PLC0415
    from app.models.lab_marker_alias import LabMarkerAlias  # noqa: PLC0415
    from app.models.lab_marker_catalog import LabMarkerCatalog  # noqa: PLC0415
    from app.models.photo import Photo  # noqa: PLC0415
    from app.models.photo_analysis import PhotoAnalysis  # noqa: PLC0415
    from app.models.photo_ingredient import PhotoIngredient  # noqa: PLC0415
    from app.models.supplement_catalog import SupplementCatalogItem  # noqa: PLC0415
    from app.models.symptom_catalog import SymptomCatalogItem  # noqa: PLC0415
    from app.models.treatment import Treatment  # noqa: PLC0415
    from app.models.weather import WeatherReading  # noqa: PLC0415

    src = _make_session(sqlite_url)
    dst = _make_session(postgres_url)

    # ------------------------------------------------------------------
    # Idempotency guard
    # ------------------------------------------------------------------
    existing = dst.execute(text("SELECT COUNT(*) FROM entries")).scalar()
    if existing:
        log.error(
            "REFUSED: target Postgres already has %d rows in 'entries'. "
            "Migration aborted to prevent duplicates.",
            existing,
        )
        src.close()
        dst.close()
        return 1

    if dry_run:
        log.info("[DRY RUN] Counting rows only — no writes will occur.")

    # ------------------------------------------------------------------
    # Step 1: Independent tables (no FKs to other app tables)
    # ------------------------------------------------------------------
    now = datetime.datetime.utcnow()
    session_where = None
    if prune_expired_sessions:
        session_where = AuthSession.expires_at >= now

    src_total_sessions = src.execute(text("SELECT COUNT(*) FROM auth_sessions")).scalar() or 0

    counts: dict[str, int] = {}

    counts["auth_sessions"] = migrate_table(src, dst, AuthSession, where=session_where, dry_run=dry_run)
    counts["supplement_catalog"] = migrate_table(src, dst, SupplementCatalogItem, dry_run=dry_run)
    counts["symptom_catalog"] = migrate_table(src, dst, SymptomCatalogItem, dry_run=dry_run)
    counts["dietary_ingredients"] = migrate_table(src, dst, DietaryIngredient, dry_run=dry_run)
    counts["weather_readings"] = migrate_table(src, dst, WeatherReading, dry_run=dry_run)
    counts["treatments"] = migrate_table(src, dst, Treatment, dry_run=dry_run)
    counts["lab_marker_catalog"] = migrate_table(src, dst, LabMarkerCatalog, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Step 2: Children of step 1
    # ------------------------------------------------------------------
    counts["ingredient_aliases"] = migrate_table(src, dst, IngredientAlias, dry_run=dry_run)
    counts["lab_marker_aliases"] = migrate_table(src, dst, LabMarkerAlias, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Step 3: Independent of step 1 children
    # ------------------------------------------------------------------
    counts["entries"] = migrate_table(src, dst, Entry, dry_run=dry_run)
    counts["labs"] = migrate_table(src, dst, Lab, dry_run=dry_run)
    counts["health_metrics"] = migrate_table(src, dst, HealthMetric, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Step 4: Children of step 3
    # ------------------------------------------------------------------
    counts["photos"] = migrate_table(src, dst, Photo, dry_run=dry_run)
    counts["lab_markers"] = migrate_table(src, dst, LabMarker, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Step 5: Children of photos
    # ------------------------------------------------------------------
    counts["photo_analyses"] = migrate_table(src, dst, PhotoAnalysis, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Step 6: Children of photo_analyses
    # ------------------------------------------------------------------
    counts["photo_ingredients"] = migrate_table(src, dst, PhotoIngredient, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Sequence resets (Postgres only; skipped on dry-run)
    # ------------------------------------------------------------------
    if not dry_run:
        tables_with_id = [
            "auth_sessions",
            "supplement_catalog",
            "symptom_catalog",
            "dietary_ingredients",
            "weather_readings",
            "treatments",
            "lab_marker_catalog",
            "ingredient_aliases",
            "lab_marker_aliases",
            "entries",
            "labs",
            "health_metrics",
            "photos",
            "lab_markers",
            "photo_analyses",
            "photo_ingredients",
        ]
        log.info("Resetting %d sequences...", len(tables_with_id))
        for tbl in tables_with_id:
            reset_sequence(dst, tbl)

    # ------------------------------------------------------------------
    # Row count report
    # ------------------------------------------------------------------
    pruned = src_total_sessions - counts["auth_sessions"]
    log.info("--- Migration summary ---")
    for tbl, n in counts.items():
        log.info("  %-30s %d", tbl, n)
    if prune_expired_sessions:
        log.info("  auth_sessions pruned (expired) %d", pruned)
    log.info("  Total rows migrated: %d", sum(counts.values()))

    if dry_run:
        log.info("[DRY RUN] Complete. No data written.")
        src.close()
        dst.close()
        return 0

    # ------------------------------------------------------------------
    # Verification phase
    # ------------------------------------------------------------------
    log.info("Running verification checks...")
    errors: list[str] = []

    # 1. FK orphan checks
    fk_errors = _fk_orphan_check(dst)
    errors.extend(fk_errors)
    if fk_errors:
        for e in fk_errors:
            log.error("FK orphan: %s", e)
    else:
        log.info("  FK orphan checks: 0 orphans")

    # 2. JSON deep-equal sampling
    json_errors = _json_sample_check(src, dst)
    errors.extend(json_errors)
    if json_errors:
        for e in json_errors:
            log.error("JSON mismatch: %s", e)
    else:
        log.info("  JSON sample checks: all match")

    src.close()
    dst.close()

    if errors:
        log.error("Verification FAILED with %d errors.", len(errors))
        return 2

    log.info("Verification PASSED. Migration complete.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate live SQLite health.db to Postgres."
    )
    parser.add_argument("--sqlite", required=True, help="Path to SQLite file")
    parser.add_argument("--postgres", required=True, help="Postgres SQLAlchemy URL (psycopg2 dialect)")
    parser.add_argument(
        "--prune-expired-sessions",
        dest="prune_expired_sessions",
        action="store_true",
        default=True,
        help="Drop auth_sessions where expires_at < now() (default: on)",
    )
    parser.add_argument(
        "--no-prune-expired-sessions",
        dest="prune_expired_sessions",
        action="store_false",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Count rows only; no writes to Postgres.",
    )
    args = parser.parse_args()

    sqlite_url = f"sqlite:///{args.sqlite}"
    exit_code = run_migration(
        sqlite_url=sqlite_url,
        postgres_url=args.postgres,
        prune_expired_sessions=args.prune_expired_sessions,
        dry_run=args.dry_run,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
