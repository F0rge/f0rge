"""One-time + catch-up migration of historical sensor data from JSON files to SQLite.

Fully idempotent via `INSERT OR IGNORE`. Two execution modes:

1. **Full migration**: readings.db does not exist yet. Parses all
   historical_data*.json* files, dedupes, creates readings.db, inserts everything.
2. **Catch-up**: readings.db exists already. Only re-parses the active file
   (historical_data.json) to pick up any readings written between the previous
   run and now, then `INSERT OR IGNORE`s them.

The `--no-move` flag skips the final step of relocating source JSONs to .migrated/.
Phase A (initial migration while the old backend still runs) should use --no-move.
Phase B (new backend's startup) runs without --no-move so it catches up + tidies up.

Run manually:
    docker exec <bk_container> python3 /app/migrate_to_sqlite.py [--no-move] [--dry-run]

Or import run_migration(data_dir, ...) from sensor_service.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone

from config import (
    COMFORT_TEMP_MIN,
    COMFORT_TEMP_MAX,
    COMFORT_HUMIDITY_MIN,
    COMFORT_HUMIDITY_MAX,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


SCHEMA_VERSION = "1"
DB_FILENAME = "readings.db"
MIGRATED_DIR = ".migrated"
ACTIVE_FILE = "historical_data.json"
SOURCE_GLOB = "historical_data*.json*"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS readings (
  timestamp TEXT PRIMARY KEY NOT NULL,
  temperature REAL NOT NULL,
  humidity REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS _meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

# Additive performance schema: a pre-rolled hourly aggregate table that the
# range='all' chart reads from instead of grouping over millions of rows.
#
# No extra indexes on `readings`: timestamp is the PRIMARY KEY, so SQLite's
# implicit sqlite_autoindex_readings_1 already serves every timestamp range
# scan / MAX(timestamp) we run. The previous idx_readings_ts duplicated it and
# idx_readings_temp_hum was never used by any query — both only cost insert
# time and ~200MB of disk; ensure_perf_schema drops them from existing DBs.
PERF_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS readings_hourly (
  bucket TEXT PRIMARY KEY NOT NULL,
  n INTEGER NOT NULL,
  t_avg REAL NOT NULL,
  t_min REAL NOT NULL,
  t_max REAL NOT NULL,
  h_avg REAL NOT NULL,
  h_min REAL NOT NULL,
  h_max REAL NOT NULL,
  t_sq_sum REAL NOT NULL,
  h_sq_sum REAL NOT NULL,
  optimal INTEGER NOT NULL
);
"""

_BACKFILL_SQL_TEMPLATE = """
INSERT INTO readings_hourly
  (bucket, n, t_avg, t_min, t_max, h_avg, h_min, h_max, t_sq_sum, h_sq_sum, optimal)
SELECT
  substr(timestamp, 1, 13) AS bucket,
  COUNT(*),
  AVG(temperature), MIN(temperature), MAX(temperature),
  AVG(humidity), MIN(humidity), MAX(humidity),
  SUM(temperature * temperature), SUM(humidity * humidity),
  SUM(CASE WHEN temperature BETWEEN ? AND ?
           AND humidity BETWEEN ? AND ? THEN 1 ELSE 0 END)
FROM readings
{where}
GROUP BY bucket
"""


def ensure_perf_schema(data_dir: str, *, verbose: bool = True) -> dict:
    """Idempotent: create readings_hourly + backfill any missing buckets.

    On first run: builds the rollup from a full scan over `readings`.
    On restart: only re-aggregates buckets at-or-after the latest already-rolled
    bucket (drops + recomputes them), so readings written between shutdown and
    the next start are picked up without a 4M-row scan.
    """
    db_path = os.path.join(data_dir, DB_FILENAME)
    result: dict = {"db_path": db_path, "started_at": _utc_now_iso()}
    if not os.path.exists(db_path):
        if verbose:
            print(f"[perf] no db at {db_path}, skipping")
        result["skipped"] = True
        return result

    conn = sqlite3.connect(db_path)
    try:
        t0 = time.time()
        conn.executescript(PERF_SCHEMA_SQL)
        # One-time cleanup on already-deployed DBs (see PERF_SCHEMA_SQL comment):
        # the PK autoindex makes idx_readings_ts redundant, idx_readings_temp_hum
        # is unused. Freed pages go to the freelist and get reused by new rows.
        conn.execute("DROP INDEX IF EXISTS idx_readings_ts")
        conn.execute("DROP INDEX IF EXISTS idx_readings_temp_hum")
        if verbose:
            print(f"[perf] readings_hourly ensured in {time.time() - t0:.2f}s")

        latest = conn.execute("SELECT MAX(bucket) FROM readings_hourly").fetchone()[0]
        comfort_params = (
            COMFORT_TEMP_MIN, COMFORT_TEMP_MAX,
            COMFORT_HUMIDITY_MIN, COMFORT_HUMIDITY_MAX,
        )
        if latest is None:
            where = ""
            params: tuple = comfort_params
            mode = "full"
        else:
            # Drop the latest bucket so we re-aggregate it cleanly; also re-aggregate
            # any newer buckets that accumulated while the service was down.
            # `timestamp >= latest` is equivalent to substr(timestamp,1,13) >= latest
            # for fixed-format ISO timestamps, but uses the PK index instead of a
            # full-table substr() scan on every restart.
            conn.execute("DELETE FROM readings_hourly WHERE bucket >= ?", (latest,))
            where = "WHERE timestamp >= ?"
            params = comfort_params + (latest,)
            mode = f"incremental from {latest}"

        t1 = time.time()
        sql = _BACKFILL_SQL_TEMPLATE.format(where=where)
        conn.execute(sql, params)
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM readings_hourly").fetchone()[0]
        if verbose:
            print(
                f"[perf] backfill mode={mode}: {total:,} total buckets "
                f"after {time.time() - t1:.2f}s"
            )
        result.update({"mode": mode, "buckets_total": total})
    finally:
        conn.close()
    return result


def db_is_initialized(db_path: str) -> bool:
    if not os.path.exists(db_path):
        return False
    try:
        c = sqlite3.connect(db_path)
        row = c.execute(
            "SELECT value FROM _meta WHERE key = 'schema_version'"
        ).fetchone()
        c.close()
        return bool(row and row[0] == SCHEMA_VERSION)
    except sqlite3.DatabaseError:
        return False


def read_source_file(path: str) -> list[tuple[str, float, float]]:
    """Parse one JSON file and return (timestamp, temperature, humidity) tuples.

    Skips entries missing any of the three required fields or with bad types.
    """
    with open(path, "r") as f:
        data = json.load(f)
    rows: list[tuple[str, float, float]] = []
    for e in data:
        ts = e.get("timestamp")
        temp = e.get("temperature")
        hum = e.get("humidity")
        if not isinstance(ts, str):
            continue
        try:
            rows.append((ts, float(temp), float(hum)))
        except (TypeError, ValueError):
            continue
    return rows


def _bulk_insert(conn: sqlite3.Connection, rows: list[tuple[str, float, float]]) -> int:
    before = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    conn.executemany(
        "INSERT OR IGNORE INTO readings (timestamp, temperature, humidity) "
        "VALUES (?, ?, ?)",
        rows,
    )
    after = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    return after - before


def run_migration(
    data_dir: str,
    *,
    dry_run: bool = False,
    move_sources: bool = True,
    verbose: bool = True,
) -> dict:
    """Migrate JSON sources in data_dir into {data_dir}/readings.db.

    Idempotent: always safe to re-run. On repeat runs, only the active file is
    re-parsed (fast catch-up path).
    """
    db_path = os.path.join(data_dir, DB_FILENAME)
    result: dict = {
        "data_dir": data_dir,
        "db_path": db_path,
        "dry_run": dry_run,
        "move_sources": move_sources,
        "started_at": _utc_now_iso(),
    }

    initialized = db_is_initialized(db_path)
    active_path = os.path.join(data_dir, ACTIVE_FILE)

    if initialized:
        # Fast catch-up path: only parse the active file.
        source_paths = [active_path] if os.path.exists(active_path) else []
        mode = "catchup"
    else:
        # Full migration path: parse all historical_data*.json* files.
        source_paths = sorted(
            glob.glob(os.path.join(data_dir, SOURCE_GLOB)),
            key=os.path.getmtime,
        )
        mode = "full"

    result["mode"] = mode

    if verbose:
        print(f"[migrate] mode={mode}, db_exists={initialized}, db_path={db_path}")
        print(f"[migrate] {len(source_paths)} source file(s) to parse:")
        for p in source_paths:
            print(f"  - {os.path.basename(p)}  ({os.path.getsize(p):,} bytes)")

    if not source_paths:
        if verbose:
            print("[migrate] nothing to parse")
        result["per_file"] = {}
        result["rows_inserted"] = 0
        result["total_elapsed_s"] = 0.0
        return result

    # Parse all relevant source files and dedupe in-memory before hitting SQLite.
    merged: dict[str, tuple[float, float]] = {}
    per_file: dict[str, int] = {}
    t0 = time.time()
    for path in source_paths:
        name = os.path.basename(path)
        t_start = time.time()
        try:
            rows = read_source_file(path)
        except Exception as e:
            print(f"  SKIP {name}: parse error {e}", file=sys.stderr)
            per_file[name] = 0
            continue
        per_file[name] = len(rows)
        for ts, temp, hum in rows:
            merged[ts] = (temp, hum)
        if verbose:
            print(f"  parsed {name}: {len(rows):,} entries in {time.time() - t_start:.1f}s")

    deduped_total = len(merged)
    parse_elapsed = time.time() - t0
    if verbose:
        print(
            f"[migrate] deduped in-memory to {deduped_total:,} unique timestamps "
            f"(parse {parse_elapsed:.1f}s)"
        )
    result["per_file"] = per_file
    result["deduped_in_memory"] = deduped_total

    if dry_run:
        if verbose:
            print("[migrate] --dry-run: not writing readings.db, not moving files")
        return result

    if deduped_total == 0:
        if verbose:
            print("[migrate] nothing to insert")
        result["rows_inserted"] = 0
        return result

    tuples = [(ts, temp, hum) for ts, (temp, hum) in merged.items()]

    t_write = time.time()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        with conn:
            inserted = _bulk_insert(conn, tuples)
            conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES ('last_migration_at', ?)",
                (_utc_now_iso(),),
            )
            conn.execute(
                "INSERT OR REPLACE INTO _meta (key, value) VALUES ('last_migration_mode', ?)",
                (mode,),
            )
            if mode == "full":
                conn.execute(
                    "INSERT OR REPLACE INTO _meta (key, value) VALUES ('full_migration_row_count', ?)",
                    (str(deduped_total),),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO _meta (key, value) VALUES ('full_migration_source_counts', ?)",
                    (json.dumps(per_file),),
                )
        total_now = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    finally:
        conn.close()
    write_elapsed = time.time() - t_write

    if verbose:
        print(
            f"[migrate] inserted {inserted:,} new rows in {write_elapsed:.1f}s "
            f"(db now has {total_now:,} rows)"
        )
    result["rows_inserted"] = inserted
    result["db_total_after"] = total_now
    result["write_elapsed_s"] = round(write_elapsed, 2)

    # Integrity check: on full migration, db row count must equal deduped total.
    if mode == "full" and total_now != deduped_total:
        raise RuntimeError(
            f"full migration row count mismatch: expected {deduped_total}, got {total_now}"
        )

    if move_sources:
        # Move ALL source files (not just the ones we parsed this run) — on a
        # catch-up run, the archive + backups are still sitting in data_dir from
        # Phase A and should also be tidied now.
        all_sources = sorted(glob.glob(os.path.join(data_dir, SOURCE_GLOB)))
        if all_sources:
            migrated_dir = os.path.join(data_dir, MIGRATED_DIR)
            os.makedirs(migrated_dir, exist_ok=True)
            for path in all_sources:
                dest = os.path.join(migrated_dir, os.path.basename(path))
                shutil.move(path, dest)
                if verbose:
                    print(f"[migrate] moved {os.path.basename(path)} -> {MIGRATED_DIR}/")
            result["migrated_dir"] = migrated_dir
            result["moved_files"] = [os.path.basename(p) for p in all_sources]
    else:
        if verbose:
            print("[migrate] --no-move: leaving source files in place")

    result["total_elapsed_s"] = round(time.time() - t0, 2)
    if verbose:
        print(f"[migrate] done in {result['total_elapsed_s']}s total")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="/app/data")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="Do not relocate source JSONs to .migrated/ after success",
    )
    args = parser.parse_args()
    try:
        run_migration(args.data_dir, dry_run=args.dry_run, move_sources=not args.no_move)
        return 0
    except Exception as e:
        print(f"[migrate] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
