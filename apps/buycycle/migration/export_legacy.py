#!/usr/bin/env python3
"""Export a consistent legacy snapshot without opening the original DB in Turso.

Run only after fencing the old writer for cutover. The supported legacy collector
shares this advisory lock. Turso lacks a read-only connect API, so only a private
temporary copy is ever opened; the original DB and its WAL are read through FDs.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

TABLES = {"listing": ("id",), "price_history": ("id", "day"), "detail": ("id",), "runs": ("day", "kind"), "country_map": ("cid",)}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def copy_regular(source, destination):
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as src:
        if not stat.S_ISREG(os.fstat(src.fileno()).st_mode):
            raise ValueError("Snapshot source must be a regular file")
        with destination.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    destination.chmod(0o600)


@contextmanager
def source_lock(source):
    lock = Path(str(source) + "-tracker.lock")
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Invalid tracker lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def export(source, destination, processing_version):
    import turso

    source = Path(source).expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ValueError("A regular legacy database is required")
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to overwrite an export")
    with source_lock(source), tempfile.TemporaryDirectory(prefix="buycycle-legacy-copy-") as temporary:
        snapshot = Path(temporary) / source.name
        before = {}
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(source) + suffix)
            if path.exists() or path.is_symlink():
                before[suffix] = (path.stat().st_size, path.stat().st_mtime_ns)
                copy_regular(path, Path(str(snapshot) + suffix))
        ledger_path = Path(str(source) + "-tracker-safety.json")
        ledger = None
        if ledger_path.exists() or ledger_path.is_symlink():
            fd = os.open(ledger_path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd) as stream:
                if os.fstat(stream.fileno()).st_size > 65536:
                    raise ValueError("Safety ledger is too large")
                ledger = json.load(stream)
        # A writer ignoring the fence is unsupported: fail rather than export an
        # apparently complete but inconsistent snapshot.
        after_suffixes = {suffix for suffix in ("", "-wal", "-shm") if Path(str(source) + suffix).exists() or Path(str(source) + suffix).is_symlink()}
        if after_suffixes != set(before):
            raise ValueError("Source files changed while snapshotting; fence every writer")
        for suffix, metadata in before.items():
            path = Path(str(source) + suffix)
            if (path.stat().st_size, path.stat().st_mtime_ns) != metadata:
                raise ValueError("Source changed while snapshotting; fence every writer")
        connection = turso.connect(str(snapshot))
        try:
            actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
            if actual != set(TABLES):
                raise ValueError("Unexpected legacy tables; review source schema before migration")
            tables, source_schema, hashes = {}, {}, {}
            for table, fields in TABLES.items():
                cursor = connection.execute(f'SELECT * FROM "{table}"')
                columns = [column[0] for column in cursor.description]
                rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
                rows.sort(key=lambda row: canonical([row[field] for field in fields]))
                tables[table] = rows
                schema_cursor = connection.execute(f'PRAGMA table_info("{table}")')
                schema_columns = [column[0] for column in schema_cursor.description]
                source_schema[table] = [dict(zip(schema_columns, row, strict=True)) for row in schema_cursor.fetchall()]
                hashes[table] = digest(rows)
        finally:
            connection.close()
        bundle = {
            "version": 1,
            "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "processing_version": processing_version,
            "tables": tables,
            "table_sha256": hashes,
            "source_schema": source_schema,
            "safety_ledger": ledger,
        }
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(bundle) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    return {"tables": {name: len(rows) for name, rows in tables.items()}, "bundle_sha256": digest(bundle)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--processing-version", required=True, help="Exact legacy code revision, or explicitly unknown-legacy")
    args = parser.parse_args()
    try:
        print(json.dumps(export(args.source, args.output, args.processing_version), sort_keys=True))
    except (OSError, ValueError, RuntimeError):
        parser.exit(1, "Legacy export failed; no source data was changed. Review fencing/schema privately.\n")


if __name__ == "__main__":
    main()
