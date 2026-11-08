"""Sensor data service backed by SQLite.

Replaces the previous in-memory-list + JSON-file implementation. Same public
interface as before so app.py and callers are unchanged.

Public methods:
- get_current_data() -> dict
- get_sensor_info() -> dict
- get_historical_data(range: str = '6h') -> list[dict]
- get_all_historical_data() -> list[dict]   # kept for compat; now just calls get_historical_data('all')
"""
from __future__ import annotations

import csv
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

import board
import busio
import adafruit_ahtx0

from config import (
    COMFORT_TEMP_MIN,
    COMFORT_TEMP_MAX,
    COMFORT_HUMIDITY_MIN,
    COMFORT_HUMIDITY_MAX,
)
from migrate_to_sqlite import PERF_SCHEMA_SQL, SCHEMA_SQL, ensure_perf_schema, run_migration

logger = logging.getLogger(__name__)

# Static sensor metadata (was previously duplicated per row in JSON).
SENSOR_INFO: dict[str, Any] = {
    "manufacturer": "Aosong",
    "description": "Temperature and Humidity Sensor",
    "interface": "I2C",
    "address": "0x38",
}

DB_FILENAME = "readings.db"
CURRENT_READING_FILENAME = "current_reading.json"

# How long to cache the range='all' rollup. Recompute cost is ~4-6s at 4M+ rows,
# data changes one row every 5s, so a 5-min TTL is invisible to users.
ALL_CACHE_TTL_SECONDS = 300

_VALID_RANGES = frozenset({"5m", "1h", "6h", "1d", "1w", "ytd", "all"})


def _pick_all_time_target(total: int) -> int:
    """Mirror the previous _improved_uniform_sampling thresholds."""
    if total > 10_000:
        return 3_000
    if total > 5_000:
        return 2_000
    if total > 2_000:
        return 1_500
    return total


def _cutoff_for(range_: str) -> str | None:
    """Return an ISO8601 cutoff timestamp for the given range, or None for 'all'."""
    if range_ not in _VALID_RANGES:
        raise ValueError(f"Unknown range: {range_}")
    if range_ == "all":
        return None
    now = datetime.now(timezone.utc)
    if range_ == "5m":
        delta = timedelta(minutes=5)
    elif range_ == "1h":
        delta = timedelta(hours=1)
    elif range_ == "6h":
        delta = timedelta(hours=6)
    elif range_ == "1d":
        delta = timedelta(days=1)
    elif range_ == "1w":
        delta = timedelta(days=7)
    elif range_ == "ytd":
        return f"{now.year}-01-01T00:00:00Z"
    return (now - delta).isoformat().replace("+00:00", "Z")


def _hourly_rows_to_series(
    rows: list[tuple],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Build chart series + aggregate dict from readings_hourly rows."""
    if not rows:
        return [], None

    series: list[dict[str, Any]] = []
    total = 0
    t_min_all = float("inf")
    t_max_all = float("-inf")
    h_min_all = float("inf")
    h_max_all = float("-inf")
    t_sum = 0.0
    h_sum = 0.0
    t_sq_sum = 0.0
    h_sq_sum = 0.0
    opt_sum = 0

    for (
        bucket, n, t_avg, t_min, t_max, h_avg, h_min, h_max,
        t_sq, h_sq, optimal,
    ) in rows:
        ts = f"{bucket}:00:00Z"
        series.append(
            {
                "timestamp": ts,
                "temperature": round(t_avg, 3),
                "humidity": round(h_avg, 3),
                "temperature_min": round(t_min, 3),
                "temperature_max": round(t_max, 3),
                "humidity_min": round(h_min, 3),
                "humidity_max": round(h_max, 3),
                "samples": n,
            }
        )
        total += n
        if t_min < t_min_all:
            t_min_all = t_min
        if t_max > t_max_all:
            t_max_all = t_max
        if h_min < h_min_all:
            h_min_all = h_min
        if h_max > h_max_all:
            h_max_all = h_max
        t_sum += t_avg * n
        h_sum += h_avg * n
        t_sq_sum += t_sq
        h_sq_sum += h_sq
        opt_sum += optimal

    if len(series) > 2000:
        target = _pick_all_time_target(len(series))
        series = SensorService._uniform_sample_dicts(series, target)

    agg = {
        "count": total,
        "temperature_min": t_min_all,
        "temperature_max": t_max_all,
        "temperature_avg": t_sum / total,
        "temperature_sqsum": t_sq_sum,
        "humidity_min": h_min_all,
        "humidity_max": h_max_all,
        "humidity_avg": h_sum / total,
        "humidity_sqsum": h_sq_sum,
        "optimal_count": opt_sum,
    }
    return series, agg


class SensorService:
    """Service for reading the ENVIRONMENT_MONITOR sensor and serving history from SQLite."""

    def __init__(self, data_dir: str = "data") -> None:
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, DB_FILENAME)
        self.current_data_file = os.path.join(data_dir, CURRENT_READING_FILENAME)
        self.sensor_info = SENSOR_INFO

        os.makedirs(data_dir, exist_ok=True)

        # Idempotent migration: creates readings.db on first boot, or catches up
        # any JSON rows written after the Phase A migration.
        try:
            run_migration(data_dir, move_sources=True, verbose=True)
        except Exception as e:
            logger.error(f"migration failed: {e}", exc_info=True)
            # Don't crash the service — fall back to whatever is in readings.db.

        # Additive perf migration: indexes + readings_hourly + backfill. Wrapped
        # so that if it fails the service still serves data from `readings`.
        try:
            ensure_perf_schema(data_dir, verbose=True)
        except Exception as e:
            logger.error(f"perf-schema migration failed: {e}", exc_info=True)

        # Open a single SQLite connection for the process. check_same_thread=False
        # allows the FastAPI request handlers AND the background sensor thread to
        # share the connection; SQLite serializes them internally.
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit — each INSERT is its own transaction
        )
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        # 32 MB page cache: enough to keep the timestamp index hot for range
        # scans over a ~4.5M-row table, still modest on a Pi shared by ~32
        # containers (was 2 MB, which forced re-reads on every window query).
        self.conn.execute("PRAGMA cache_size = -32768")
        # Guarantee the schema exists even when the migrations above had nothing
        # to do (fresh install with no readings.db and no JSON sources —
        # run_migration returns early without creating the DB in that case, and
        # the sensor loop would then fail every INSERT with "no such table").
        self.conn.executescript(SCHEMA_SQL)
        self.conn.executescript(PERF_SCHEMA_SQL)
        self._conn_lock = threading.Lock()
        self._sensor_data_lock = threading.Lock()

        # range='all' rollup cache. Holds (downsampled series, aggregate dict, mtime).
        # Recompute on first miss, then every ALL_CACHE_TTL_SECONDS.
        self._all_cache_lock = threading.Lock()
        self._all_cache_series: list[dict[str, Any]] | None = None
        self._all_cache_agg: dict[str, Any] | None = None
        self._all_cache_expires_at: float = 0.0

        self.sensor_data: dict[str, Any] = {
            "temperature": 0.0,
            "humidity": 0.0,
            "raw_temperature": None,
            "raw_humidity": None,
            "last_update": "",
            "status": "initializing",
            "sensor_info": self.sensor_info,
        }

        self._load_current_data()

        # Warm the 'all' rollup cache in the background so the first user to
        # open the dashboard with range=all doesn't wait several seconds.
        threading.Thread(target=self.warm_all_cache, daemon=True).start()

        # Hardware init
        self.aht: adafruit_ahtx0.AHTx0 | None = None
        self._initialize_sensor()
        if self.aht is not None:
            self._start_background_thread()

    # -------- sensor hardware --------

    def _initialize_sensor(self) -> None:
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.aht = adafruit_ahtx0.AHTx0(i2c)
            with self._sensor_data_lock:
                self.sensor_data["status"] = "connected"
            logger.info("ENVIRONMENT_MONITOR sensor initialized successfully")
        except Exception as e:
            with self._sensor_data_lock:
                self.sensor_data["status"] = f"error: {e}"
            self.aht = None
            logger.error(f"Failed to initialize ENVIRONMENT_MONITOR sensor: {e}")

    def _start_background_thread(self) -> None:
        t = threading.Thread(target=self._read_sensor_loop, daemon=True)
        t.start()
        logger.info("Sensor reading thread started")

    def _read_sensor_loop(self) -> None:
        # Buffer readings and flush in batches every BATCH_SIZE samples (~30s)
        # to reduce fsync overhead. The current_reading.json file is still
        # written on every read so the dashboard stays fresh.
        BATCH_SIZE = 6
        batch: list[tuple[str, float, float]] = []
        consecutive_failures = 0

        while True:
            try:
                if self.aht is not None:
                    raw_t = self.aht.temperature
                    raw_h = self.aht.relative_humidity
                    raw_temperature = round(raw_t, 4)
                    raw_humidity = round(raw_h, 4)
                    temperature = round(raw_t, 2)
                    humidity = round(raw_h, 2)
                    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    consecutive_failures = 0

                    with self._sensor_data_lock:
                        self.sensor_data.update(
                            {
                                "temperature": temperature,
                                "humidity": humidity,
                                "raw_temperature": raw_temperature,
                                "raw_humidity": raw_humidity,
                                "last_update": timestamp,
                                "status": "connected",
                                "sensor_info": self.sensor_info,
                            }
                        )

                    # Persist current reading atomically (tmp + rename) so a crash
                    # mid-write can't leave a half-written JSON.
                    try:
                        tmp_path = self.current_data_file + ".tmp"
                        with open(tmp_path, "w") as f:
                            json.dump(self.sensor_data, f, indent=2)
                        os.replace(tmp_path, self.current_data_file)
                    except Exception as e:
                        logger.error(f"failed to write current_reading.json: {e}")

                    batch.append((timestamp, temperature, humidity))
                    if len(batch) >= BATCH_SIZE:
                        try:
                            with self._conn_lock:
                                # executemany batches the inserts; with autocommit
                                # the driver still issues a single transaction here
                                # because we're inside the same lock.
                                self.conn.executemany(
                                    "INSERT OR IGNORE INTO readings (timestamp, temperature, humidity) "
                                    "VALUES (?, ?, ?)",
                                    batch,
                                )
                                # Hourly rollup gets one upsert per reading — cheap (single row).
                                for ts, t, h in batch:
                                    self._upsert_hourly_bucket(ts, t, h)
                        except Exception as e:
                            logger.error(f"failed to flush reading batch: {e}")
                        finally:
                            batch.clear()

                    logger.debug(f"Sensor reading: {temperature:.2f}°C, {humidity:.2f}%")
                else:
                    with self._sensor_data_lock:
                        self.sensor_data["status"] = "sensor not available"
                    consecutive_failures += 1
            except Exception as e:
                with self._sensor_data_lock:
                    self.sensor_data["status"] = f"error: {e}"
                logger.error(f"Sensor reading error: {e}")
                consecutive_failures += 1

            # Reconnect attempt after sustained failures.
            if consecutive_failures > 0 and consecutive_failures % 10 == 0:
                logger.warning(
                    f"sensor has failed {consecutive_failures} times in a row, "
                    f"attempting re-initialization"
                )
                try:
                    self._initialize_sensor()
                except Exception as e:
                    logger.error(f"sensor re-init raised: {e}")

            time.sleep(5)

    # -------- persistence helpers --------

    def _load_current_data(self) -> None:
        if os.path.exists(self.current_data_file):
            try:
                with open(self.current_data_file, "r") as f:
                    loaded = json.load(f)
                if "sensor_info" not in loaded:
                    loaded["sensor_info"] = self.sensor_info
                self.sensor_data = loaded
            except Exception as e:
                logger.error(f"error loading current_reading.json: {e}")

    # -------- public API --------

    def get_current_data(self) -> dict[str, Any]:
        with self._sensor_data_lock:
            return self.sensor_data.copy()

    def get_live_reading(self) -> dict[str, Any]:
        """High-precision raw sensor values — not persisted, served live."""
        with self._sensor_data_lock:
            return {
                "temperature": self.sensor_data.get("raw_temperature"),
                "humidity": self.sensor_data.get("raw_humidity"),
                "timestamp": self.sensor_data.get("last_update"),
            }

    def get_sensor_info(self) -> dict[str, Any]:
        return self.sensor_info.copy()

    def get_historical_data(self, range_: str = "6h") -> list[dict[str, Any]]:
        """Return rows for the requested time range.

        For '5m', '1h', '6h': returns every row in the window, ordered by timestamp ascending.
        For '1d' and '1w': decimates inside SQLite (stride sampling on rowid) to ~1k
        points so we never pull six-figure row counts into Python.
        For 'ytd': hourly-bucketed rollup from readings_hourly since year start.
        For 'all': returns hourly-bucketed rollup from readings_hourly (TTL-cached).
        """
        if range_ not in _VALID_RANGES:
            raise ValueError(f"Unknown range: {range_}")

        if range_ == "all":
            series, _ = self._get_all_rollup()
            return series

        if range_ == "ytd":
            cutoff = _cutoff_for("ytd")
            series, _ = self._get_hourly_series_since(cutoff[:13])
            return series

        cutoff = _cutoff_for(range_)

        # For 1d/1w windows, decimate inside SQLite so we never pull 100k+ rows
        # into Python just to throw most away. Sample stride is chosen from
        # COUNT(*) over the window; the latest timestamp is always kept so the
        # chart's right edge stays current.
        if range_ in ("1d", "1w"):
            target = 1000 if range_ == "1d" else 1200
            with self._conn_lock:
                total = self.conn.execute(
                    "SELECT COUNT(*) FROM readings WHERE timestamp >= ?", (cutoff,)
                ).fetchone()[0]
                if total <= target:
                    rows = self.conn.execute(
                        "SELECT timestamp, temperature, humidity FROM readings "
                        "WHERE timestamp >= ? ORDER BY timestamp",
                        (cutoff,),
                    ).fetchall()
                else:
                    stride = max(1, total // target)
                    rows = self.conn.execute(
                        "SELECT timestamp, temperature, humidity FROM readings "
                        "WHERE timestamp >= ? "
                        "AND (ABS(rowid) % ? = 0 "
                        "     OR timestamp = (SELECT MAX(timestamp) FROM readings "
                        "                     WHERE timestamp >= ?)) "
                        "ORDER BY timestamp",
                        (cutoff, stride, cutoff),
                    ).fetchall()
            return [self._row_to_dict(r) for r in rows]

        with self._conn_lock:
            cur = self.conn.execute(
                "SELECT timestamp, temperature, humidity FROM readings "
                "WHERE timestamp >= ? ORDER BY timestamp",
                (cutoff,),
            )
            rows = cur.fetchall()

        return [self._row_to_dict(r) for r in rows]

    def get_all_historical_data(self) -> list[dict[str, Any]]:
        """Backward-compat alias for get_historical_data('all')."""
        return self.get_historical_data("all")

    def iter_csv_rows(self, batch_size: int = 10_000):
        """Yield CSV chunks for EVERY raw reading, oldest first.

        The download endpoint must export full-resolution data — never the
        chart rollup that get_historical_data('all') returns. Streams in
        ~400KB chunks instead of materializing a 4.5M-row string, and uses its
        own read-only connection so a slow download never holds _conn_lock
        (WAL lets this reader run alongside the sensor writer thread).

        check_same_thread=False: Starlette iterates this sync generator in a
        threadpool and may resume/finalize it on a different thread than the one
        that opened the connection, so the finally-block close() would otherwise
        raise sqlite3.ProgrammingError. The connection is only ever touched
        sequentially by this one generator, never concurrently, so dropping the
        same-thread check is safe.
        """
        header = StringIO()
        csv.writer(header).writerow(["Timestamp", "Temperature (°C)", "Humidity (%)"])
        yield header.getvalue()

        conn = sqlite3.connect(
            f"file:{self.db_path}?mode=ro", uri=True, check_same_thread=False
        )
        try:
            cur = conn.execute(
                "SELECT timestamp, temperature, humidity FROM readings "
                "ORDER BY timestamp"
            )
            while rows := cur.fetchmany(batch_size):
                buf = StringIO()
                csv.writer(buf).writerows(rows)
                yield buf.getvalue()
        finally:
            conn.close()

    def _upsert_hourly_bucket(
        self, timestamp: str, temperature: float, humidity: float
    ) -> None:
        """Merge a single new reading into its hourly bucket in readings_hourly.

        Caller MUST hold self._conn_lock (this runs inside the same lock the
        reading INSERT used). Uses SQLite UPSERT so the bucket is created on
        first sight and incrementally updated thereafter — no rescans.
        """
        bucket = timestamp[:13]  # "YYYY-MM-DDTHH"
        optimal = 1 if (
            COMFORT_TEMP_MIN <= temperature <= COMFORT_TEMP_MAX
            and COMFORT_HUMIDITY_MIN <= humidity <= COMFORT_HUMIDITY_MAX
        ) else 0
        t_sq = temperature * temperature
        h_sq = humidity * humidity
        # SQLite UPSERT: column refs in the UPDATE clause read OLD row values, so
        # `n` and `t_avg` here are the pre-update values regardless of SET order.
        self.conn.execute(
            """
            INSERT INTO readings_hourly
              (bucket, n, t_avg, t_min, t_max, h_avg, h_min, h_max, t_sq_sum, h_sq_sum, optimal)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket) DO UPDATE SET
              t_avg = (t_avg * n + excluded.t_avg) / (n + 1),
              t_min = MIN(t_min, excluded.t_min),
              t_max = MAX(t_max, excluded.t_max),
              h_avg = (h_avg * n + excluded.h_avg) / (n + 1),
              h_min = MIN(h_min, excluded.h_min),
              h_max = MAX(h_max, excluded.h_max),
              t_sq_sum = t_sq_sum + excluded.t_sq_sum,
              h_sq_sum = h_sq_sum + excluded.h_sq_sum,
              optimal = optimal + excluded.optimal,
              n = n + 1
            """,
            (bucket, temperature, temperature, temperature,
             humidity, humidity, humidity, t_sq, h_sq, optimal),
        )

    def _fetch_hourly_rows(self, bucket_cutoff: str | None = None) -> list[tuple]:
        """Read readings_hourly buckets, optionally filtered from bucket_cutoff."""
        sql = (
            "SELECT bucket, n, t_avg, t_min, t_max, h_avg, h_min, h_max, "
            "t_sq_sum, h_sq_sum, optimal "
            "FROM readings_hourly "
        )
        with self._conn_lock:
            if bucket_cutoff is None:
                return self.conn.execute(sql + "ORDER BY bucket").fetchall()
            return self.conn.execute(
                sql + "WHERE bucket >= ? ORDER BY bucket",
                (bucket_cutoff,),
            ).fetchall()

    def _get_hourly_series_since(
        self, bucket_cutoff: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Hourly rollup series (and aggregate) without touching the 'all' cache."""
        rows = self._fetch_hourly_rows(bucket_cutoff)
        return _hourly_rows_to_series(rows)

    def _get_all_rollup(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Return (series, aggregate) for range='all', using a TTL'd cache.

        Reads pre-computed buckets from readings_hourly (maintained incrementally
        by _upsert_hourly_bucket on each insert + backfilled at startup), so this
        no longer scans `readings` even for a cache miss.
        """
        now = time.monotonic()
        with self._all_cache_lock:
            if (
                self._all_cache_series is not None
                and now < self._all_cache_expires_at
            ):
                return self._all_cache_series, self._all_cache_agg

        series, agg = self._get_hourly_series_since(None)

        with self._all_cache_lock:
            self._all_cache_series = series
            self._all_cache_agg = agg
            self._all_cache_expires_at = now + ALL_CACHE_TTL_SECONDS

        return series, agg

    def warm_all_cache(self) -> None:
        """Best-effort cache warm. Called from a daemon thread at startup so the
        first user to click 'All' doesn't pay the 5s computation cost."""
        try:
            self._get_all_rollup()
            logger.info("range='all' rollup cache warmed")
        except Exception as e:
            logger.error(f"failed to warm 'all' cache: {e}")

    def get_aggregate_metrics(self, range_: str) -> dict[str, Any] | None:
        """Compute min/max/avg/std-dev over the full (non-downsampled) window in SQL.

        Returns None if the range cannot be aggregated server-side, so callers
        can fall back to Python-side computation on the downsampled list.
        """
        if range_ == "all":
            # Hot path: served from the same cache as the series, so an "all"
            # dashboard load is a single SQL pass (or zero passes if cached).
            _, agg = self._get_all_rollup()
            return agg

        cutoff = _cutoff_for(range_)
        sql = (
            "SELECT COUNT(*), "
            "MIN(temperature), MAX(temperature), AVG(temperature), "
            "MIN(humidity), MAX(humidity), AVG(humidity), "
            "SUM(temperature*temperature), SUM(humidity*humidity), "
            "SUM(CASE WHEN temperature >= ? AND temperature <= ? "
            "AND humidity >= ? AND humidity <= ? THEN 1 ELSE 0 END) "
            "FROM readings"
        )
        params: tuple = (
            COMFORT_TEMP_MIN, COMFORT_TEMP_MAX,
            COMFORT_HUMIDITY_MIN, COMFORT_HUMIDITY_MAX,
        )
        if cutoff is not None:
            sql += " WHERE timestamp >= ?"
            params = params + (cutoff,)
        with self._conn_lock:
            row = self.conn.execute(sql, params).fetchone()
        if not row or not row[0]:
            return None
        count, t_min, t_max, t_avg, h_min, h_max, h_avg, t_sqsum, h_sqsum, optimal = row
        return {
            "count": count,
            "temperature_min": t_min,
            "temperature_max": t_max,
            "temperature_avg": t_avg,
            "temperature_sqsum": t_sqsum,
            "humidity_min": h_min,
            "humidity_max": h_max,
            "humidity_avg": h_avg,
            "humidity_sqsum": h_sqsum,
            "optimal_count": optimal,
        }

    def _row_to_dict(self, row: tuple[str, float, float]) -> dict[str, Any]:
        # No sensor_info: static metadata repeated per point was ~40% of the
        # historical payload and unread by the frontend (see HistoricalEntry).
        ts, temp, hum = row
        return {
            "timestamp": ts,
            "temperature": temp,
            "humidity": hum,
        }

    @staticmethod
    def _uniform_sample(rows: list[tuple], target: int) -> list[tuple]:
        """Downsample a list of rows to `target` points, keeping first + last."""
        if len(rows) <= target:
            return rows
        if target <= 2:
            return [rows[0], rows[-1]]
        out = [rows[0]]
        middle = rows[1:-1]
        middle_target = target - 2
        step = len(middle) / middle_target
        for i in range(middle_target):
            out.append(middle[int(i * step)])
        out.append(rows[-1])
        return out

    @staticmethod
    def _uniform_sample_dicts(items: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
        if len(items) <= target:
            return items
        if target <= 2:
            return [items[0], items[-1]]
        out = [items[0]]
        middle = items[1:-1]
        middle_target = target - 2
        step = len(middle) / middle_target
        for i in range(middle_target):
            out.append(middle[int(i * step)])
        out.append(items[-1])
        return out
