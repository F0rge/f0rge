"""Idempotent Cin7 Core export -> Firstout.

Dry-run is the default. Pass ``--commit`` to keep the upsert.

The command refuses any database URL that is not local unless
``FIRSTOUT_CIN7_IMPORT_TARGET=firstout`` (the Firstout Railway database; Firstout is
main-only). ``develop`` is still accepted for older runbooks. It always refuses URLs
that look like Marrow.

    python -m app.commands.import_cin7 --export-dir /path/to/cin7
    python -m app.commands.import_cin7 --export-dir /path/to/cin7 --commit

The admin UI at ``/cin7-import`` calls the same ``run_import`` service.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

BANNED_URL_MARKERS = (
    "marrow",
    "pgvector",
    "zoological",
    "healthtracker",
    "production",
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ALLOWED_TARGETS = {"firstout", "develop"}


def assert_safe_database_url(url: str) -> None:
    lowered = url.lower()
    for marker in BANNED_URL_MARKERS:
        if marker in lowered:
            raise SystemExit(f"Refusing database URL that mentions {marker}.")
    host = (urlparse(url.replace("+asyncpg", "")).hostname or "").lower()
    if host in LOCAL_HOSTS:
        return
    if os.environ.get("FIRSTOUT_CIN7_IMPORT_TARGET") in ALLOWED_TARGETS:
        return
    raise SystemExit(
        "Refusing non-local database. Use a local Postgres URL, or set "
        "FIRSTOUT_CIN7_IMPORT_TARGET=firstout for the Firstout Railway database."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a Cin7 Core export into Firstout.")
    parser.add_argument(
        "--export-dir", required=True, type=Path, help="Directory of Cin7 CSV/XLSX files"
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Write the upsert. Without this flag the transaction is rolled back.",
    )
    return parser


async def _run(export_dir: Path, commit: bool) -> int:
    from app.config import settings
    from app.database import async_session_maker
    from app.services.cin7_import import format_report, run_import

    assert_safe_database_url(settings.database_url)
    if not export_dir.is_dir():
        print(f"Export directory does not exist: {export_dir}", file=sys.stderr)
        return 2
    async with async_session_maker() as session:
        assert isinstance(session, AsyncSession)
        report = await run_import(session, export_dir)
        report.dry_run = not commit
        if commit:
            await session.commit()
        else:
            await session.rollback()
    print(format_report(report), end="")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = _parser().parse_args(argv)
    return asyncio.run(_run(args.export_dir, args.commit))


if __name__ == "__main__":
    raise SystemExit(main())
