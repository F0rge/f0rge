"""Read-only opener for the tracker database.

The file is the pyturso database the tracker writes (BUYCYCLE_DB, defaulting to
tracker/buycycle.turso.db, or /data/buycycle.turso.db in the container). It is a
SQLite file. mode=ro rejects writes; immutable=1 avoids lock files so a read-only
volume mount works. There is no write path.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from buycycle_mcp._tracker import tracker_dir


def db_path() -> str:
    """Same path rule as tracker/storage.py: BUYCYCLE_DB or tracker/buycycle.turso.db."""
    configured = os.environ.get("BUYCYCLE_DB")
    if configured:
        return configured
    return str(tracker_dir() / "buycycle.turso.db")


def connect_readonly(path: Optional[str] = None) -> sqlite3.Connection:
    database = path or db_path()
    if not os.path.isfile(database):
        raise FileNotFoundError(f"tracker database not found: {database}")
    uri = Path(database).resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


@contextmanager
def readonly_db(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    conn = connect_readonly(path)
    try:
        yield conn
    finally:
        conn.close()
