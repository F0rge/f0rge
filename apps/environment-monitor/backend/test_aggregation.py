"""Runnable correctness checks for the historical-data aggregation paths.

Plain asserts, nothing beyond requirements.txt (stdlib only, in fact):

    python3 test_aggregation.py

Hardware modules (board/busio/adafruit_ahtx0) are force-stubbed so
SensorService can be constructed on any machine: it detects the missing
sensor, skips the reader thread, and the whole SQLite path stays real.

Covers the regressions that have actually happened in this app's history:
- range='all' must be an aggregated ~hourly series, not raw rows (perf)
- the newest data must be included in every series (ccc8390)
- the CSV export must be full resolution, not the chart rollup
- fresh boot with no JSON sources must still create the schema
- restart backfill must pick up rows written while the service was down
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Force stubs (not setdefault): never touch real I2C hardware from a test.
for _name in ("board", "busio", "adafruit_ahtx0"):
    sys.modules[_name] = types.ModuleType(_name)

from migrate_to_sqlite import ensure_perf_schema  # noqa: E402
from services.sensor_service import SensorService  # noqa: E402

_orig_init = SensorService.__init__


def _init_after_cache_warm(self, *args, **kwargs):
    """Production starts a daemon thread that queries SQLite. Closing that
    connection, or deleting the temp dir, while the thread is inside
    execute() segfaults. Wait until the warm finishes before the check runs."""
    _orig_init(self, *args, **kwargs)
    for _ in range(500):
        with self._all_cache_lock:
            if self._all_cache_series is not None:
                return
        time.sleep(0.01)


SensorService.__init__ = _init_after_cache_warm


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def insert(svc: SensorService, rows: list[tuple[str, float, float]]) -> None:
    """Mirror the sensor write path: raw INSERT + hourly-bucket upsert."""
    with svc._conn_lock:
        svc.conn.executemany(
            "INSERT OR IGNORE INTO readings (timestamp, temperature, humidity) "
            "VALUES (?, ?, ?)",
            rows,
        )
        for ts, t, h in rows:
            svc._upsert_hourly_bucket(ts, t, h)


def fetch_all(svc: SensorService) -> list[dict]:
    """get_historical_data('all') with the TTL cache forced cold.

    The startup warm thread may have cached an empty series before our test
    inserts; retry briefly in case that thread is still mid-flight.
    """
    for _ in range(50):
        with svc._all_cache_lock:
            svc._all_cache_expires_at = 0.0
        series = svc.get_historical_data("all")
        if series:
            return series
        time.sleep(0.05)
    return svc.get_historical_data("all")


def test_fresh_boot_creates_schema() -> None:
    """No readings.db, no JSON sources: init must still create all tables
    (previously the sensor loop failed every INSERT with 'no such table')."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        tables = {
            r[0] for r in svc.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"readings", "readings_hourly", "_meta"} <= tables, tables
        # No secondary indexes: the timestamp PK autoindex covers range scans.
        idx = {
            r[0] for r in svc.conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='readings'"
            )
        }
        assert not any(i.startswith("idx_") for i in idx), idx
        insert(svc, [(iso(datetime.now(timezone.utc)), 21.0, 50.0)])
        svc.conn.close()


def test_legacy_indexes_dropped_on_startup() -> None:
    """DBs deployed with idx_readings_ts / idx_readings_temp_hum lose them on
    the next ensure_perf_schema run (they only cost write time and disk)."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        insert(svc, [(iso(datetime.now(timezone.utc)), 21.0, 50.0)])
        with svc._conn_lock:
            svc.conn.execute("CREATE INDEX idx_readings_ts ON readings(timestamp)")
            svc.conn.execute(
                "CREATE INDEX idx_readings_temp_hum "
                "ON readings(temperature DESC, humidity DESC)"
            )
        ensure_perf_schema(tmp, verbose=False)
        idx = {
            r[0] for r in svc.conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='readings'"
            )
        }
        assert not any(i.startswith("idx_") for i in idx), idx
        svc.conn.close()


def test_all_rollup_math_order_and_newest() -> None:
    """range='all': one point per hourly bucket, correct averages,
    chronological, and the newest bucket present (ccc8390 guard)."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        base = datetime(2026, 7, 1, 5, 0, 0, tzinfo=timezone.utc)
        insert(svc, [
            (iso(base.replace(minute=10)), 20.0, 40.0),
            (iso(base.replace(minute=50)), 22.0, 50.0),          # 05h: t=21, h=45
            (iso(base.replace(hour=6, minute=30)), 24.0, 60.0),  # 06h: t=24, h=60
            (iso(base.replace(hour=7, minute=1)), 18.0, 30.0),
            (iso(base.replace(hour=7, minute=2)), 20.0, 40.0),
            (iso(base.replace(hour=7, minute=59)), 25.0, 50.0),  # 07h: t=21, h=40
        ])
        series = fetch_all(svc)
        assert len(series) == 3, series
        ts = [e["timestamp"] for e in series]
        assert ts == sorted(ts), ts
        assert ts[0] == "2026-07-01T05:00:00Z"
        assert ts[-1] == "2026-07-01T07:00:00Z"  # newest bucket included
        assert abs(series[0]["temperature"] - 21.0) < 1e-9
        assert abs(series[0]["humidity"] - 45.0) < 1e-9
        assert abs(series[1]["temperature"] - 24.0) < 1e-9
        assert abs(series[2]["temperature"] - 21.0) < 1e-9
        assert series[2]["samples"] == 3
        for e in series:  # HistoricalEntry response shape
            assert {"timestamp", "temperature", "humidity"} <= e.keys(), e
            assert "sensor_info" not in e, "static metadata must not repeat per point"
        svc.conn.close()


def test_backfill_and_incremental_restart() -> None:
    """Full backfill reproduces the incrementally-upserted buckets, and the
    restart path picks up rows written while the service was down."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        base = datetime(2026, 6, 30, 22, 0, 0, tzinfo=timezone.utc)
        insert(svc, [
            (iso(base.replace(minute=5)), 20.0, 40.0),
            (iso(base.replace(minute=45)), 24.0, 60.0),           # 22h
            (iso(base.replace(hour=23, minute=30)), 22.0, 50.0),  # 23h (latest)
        ])

        def buckets() -> dict:
            return {
                r[0]: r[1:] for r in svc.conn.execute(
                    "SELECT bucket, n, t_avg, t_min, t_max, h_avg, h_min, h_max "
                    "FROM readings_hourly ORDER BY bucket"
                )
            }

        upserted = buckets()
        with svc._conn_lock:
            svc.conn.execute("DELETE FROM readings_hourly")
        ensure_perf_schema(tmp, verbose=False)  # full backfill
        backfilled = buckets()
        assert upserted.keys() == backfilled.keys(), (upserted, backfilled)
        for b in upserted:
            for got, want in zip(backfilled[b], upserted[b]):
                assert abs(got - want) < 1e-9, (b, backfilled[b], upserted[b])

        # "Service down": plain INSERTs, no upsert — one more row in the
        # latest bucket, one in a brand-new later bucket.
        with svc._conn_lock:
            svc.conn.executemany(
                "INSERT INTO readings (timestamp, temperature, humidity) "
                "VALUES (?, ?, ?)",
                [
                    (iso(base.replace(hour=23, minute=50)), 26.0, 70.0),
                    (iso(base + timedelta(hours=2, minutes=10)), 19.0, 35.0),
                ],
            )
        ensure_perf_schema(tmp, verbose=False)  # incremental restart catch-up
        after = buckets()
        assert after["2026-06-30T23"][0] == 2, after      # n grew 1 -> 2
        assert abs(after["2026-06-30T23"][1] - 24.0) < 1e-9  # avg(22, 26)
        assert after["2026-07-01T00"][0] == 1, after      # new bucket appeared
        svc.conn.close()


def test_1d_decimation_keeps_newest_and_order() -> None:
    """1d window is decimated in SQL but must stay chronological and always
    include the newest reading (the chart's right edge)."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        now = datetime.now(timezone.utc)
        rows = [
            (iso(now - timedelta(seconds=20 * i)), 21.0, 50.0)
            for i in range(2500)
        ]
        rows.reverse()  # oldest first, like real inserts
        with svc._conn_lock:
            svc.conn.executemany(
                "INSERT INTO readings (timestamp, temperature, humidity) "
                "VALUES (?, ?, ?)",
                rows,
            )
        out = svc.get_historical_data("1d")
        assert 0 < len(out) <= 1300, len(out)  # decimated, not raw 2500
        ts = [e["timestamp"] for e in out]
        assert ts == sorted(ts), "series must be chronological"
        assert ts[-1] == rows[-1][0], "newest reading must be included"
        assert "sensor_info" not in out[0], "static metadata must not repeat per point"
        svc.conn.close()


def test_5m_window_span() -> None:
    """5m window returns only raw rows from the last ~5 minutes, chronological."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        now = datetime.now(timezone.utc)
        rows = [
            (iso(now - timedelta(minutes=10)), 19.0, 40.0),
            (iso(now - timedelta(minutes=7)), 20.0, 45.0),
            (iso(now - timedelta(minutes=4)), 21.0, 50.0),
            (iso(now - timedelta(minutes=2)), 22.0, 55.0),
            (iso(now - timedelta(seconds=30)), 23.0, 60.0),
        ]
        insert(svc, rows)
        out = svc.get_historical_data("5m")
        ts = [e["timestamp"] for e in out]
        assert ts == sorted(ts), "series must be chronological"
        cutoff = now - timedelta(minutes=5)
        for e in out:
            assert datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) >= cutoff
        assert len(out) == 3, out
        assert out[0]["timestamp"] == rows[2][0]
        assert out[-1]["timestamp"] == rows[-1][0]
        svc.conn.close()


def test_ytd_filters_prior_year() -> None:
    """ytd series uses hourly buckets from Jan 1 this year only."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        year = datetime.now(timezone.utc).year
        insert(svc, [
            (iso(datetime(year - 1, 12, 31, 23, 30, tzinfo=timezone.utc)), 18.0, 35.0),
            (iso(datetime(year, 1, 1, 1, 0, tzinfo=timezone.utc)), 20.0, 40.0),
            (iso(datetime(year, 1, 1, 12, 0, tzinfo=timezone.utc)), 22.0, 50.0),
            (iso(datetime(year, 1, 2, 8, 0, tzinfo=timezone.utc)), 24.0, 60.0),
        ])
        series = svc.get_historical_data("ytd")
        assert series, series
        ts = [e["timestamp"] for e in series]
        assert ts == sorted(ts), ts
        assert ts[0] >= f"{year}-01-01T00:00:00Z"
        assert all(t.startswith(str(year)) for t in ts), ts
        assert len(series) == 3, series
        for e in series:
            assert "temperature_min" in e and "samples" in e, e
        svc.conn.close()


def test_unknown_range_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        try:
            svc.get_historical_data("nope")
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "nope" in str(e)
        svc.conn.close()


def test_csv_stream_full_resolution() -> None:
    """The CSV export streams EVERY raw row (header + N lines, oldest first)
    while the chart 'all' series stays downsampled."""
    with tempfile.TemporaryDirectory() as tmp:
        svc = SensorService(data_dir=tmp)
        now = datetime.now(timezone.utc)
        n = 25_000
        rows = [
            (iso(now - timedelta(seconds=5 * i)), 21.5, 55.5)
            for i in range(n)
        ]
        rows.reverse()
        with svc._conn_lock:
            svc.conn.executemany(
                "INSERT INTO readings (timestamp, temperature, humidity) "
                "VALUES (?, ?, ?)",
                rows,
            )
            for ts, t, h in rows[::500]:  # sparse rollup, enough to contrast
                svc._upsert_hourly_bucket(ts, t, h)
        chunks = list(svc.iter_csv_rows(batch_size=10_000))
        assert len(chunks) == 1 + 3, len(chunks)  # header + ceil(25000/10000)
        lines = "".join(chunks).strip().split("\r\n")
        assert lines[0] == "Timestamp,Temperature (°C),Humidity (%)", lines[0]
        assert len(lines) == n + 1, len(lines)
        assert lines[1].startswith(rows[0][0]), "CSV must be oldest-first"
        assert len(fetch_all(svc)) < n, "chart series must stay downsampled"
        svc.conn.close()


if __name__ == "__main__":
    import subprocess

    tests = [
        fn for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    # One process per check. SensorService starts a daemon thread that keeps
    # the SQLite connection; deleting the temp dir while that thread is still
    # in a query segfaults the next check in the same process.
    if len(sys.argv) == 2 and sys.argv[1].startswith("test_"):
        globals()[sys.argv[1]]()
        raise SystemExit(0)
    for fn in tests:
        subprocess.check_call([sys.executable, __file__, fn.__name__])
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} checks passed")
