"""One-off backfill: run AI food analysis on all photos that lack it.

Usage:
    cd backend && uv run python -m scripts.backfill_photo_analysis [--dry-run] [--delay SECS]

Finds every photo without a completed analysis and calls the same
trigger_analysis_background() used by the normal upload flow.
trigger_analysis_background is async and opens its own DB session;
this script drives it via asyncio.run().
"""

from __future__ import annotations

import argparse
import asyncio
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.food_analysis_orchestrator import trigger_analysis_background
from scripts._db import SyncSession

SKIP_STATUSES = {"complete", "confirmed", "analyzing", "needs_review"}


def find_unprocessed_photos(session: Session) -> list[tuple[int, str, str | None]]:
    """Return (photo_id, filename, current_status) for photos needing analysis."""
    rows = session.execute(
        select(Photo.id, Photo.filename, PhotoAnalysis.status).outerjoin(
            PhotoAnalysis, Photo.id == PhotoAnalysis.photo_id
        )
    ).all()
    return [(pid, fname, status) for pid, fname, status in rows if status not in SKIP_STATUSES]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill AI photo analysis")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List photos that would be processed without calling the API",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between API calls (default: 2)",
    )
    args = parser.parse_args()

    with SyncSession() as session:
        unprocessed = find_unprocessed_photos(session)

    if not unprocessed:
        print("All photos already have a completed analysis. Nothing to do.")
        return

    print(f"Found {len(unprocessed)} photo(s) to process:\n")
    for pid, fname, status in unprocessed:
        label = status or "no analysis"
        print(f"  photo {pid}: {fname} ({label})")

    if args.dry_run:
        print("\n--dry-run: stopping here.")
        return

    print()
    for i, (pid, fname, _) in enumerate(unprocessed, 1):
        print(f"[{i}/{len(unprocessed)}] Analyzing photo {pid} ({fname})...")
        asyncio.run(trigger_analysis_background(pid))

        with SyncSession() as session:
            analysis = session.execute(
                select(PhotoAnalysis).where(PhotoAnalysis.photo_id == pid)
            ).scalar_one_or_none()
            if analysis and analysis.status == "complete":
                count = len(analysis.ingredients) if analysis.ingredients else 0
                print(f"  -> {analysis.dish_name} ({count} ingredients)")
            elif analysis and analysis.status == "failed":
                msg = analysis.error_message[:120] if analysis.error_message else "unknown"
                print(f"  -> FAILED: {msg}")
            else:
                status_val = analysis.status if analysis else "no record"
                print(f"  -> status: {status_val}")

        if i < len(unprocessed):
            time.sleep(args.delay)

    print(f"\nDone. Processed {len(unprocessed)} photo(s).")


if __name__ == "__main__":
    main()
