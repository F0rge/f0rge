"""Backfill report: diff legacy diet_risk strings against photo-derived flags.

Walks every Entry in the database, computes compute_photo_signal() for each,
and writes a CSV report comparing photo-derived flags to the legacy diet_risk
field. Read-only — does NOT modify any row.

Usage:
    cd backend && uv run python -m scripts.backfill_effective_flags

Output: backfill_report.csv in the working directory.
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import app.models  # noqa: F401 - registers all ORM classes with Base.metadata
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.services.diet_flags import compute_photo_signal
from scripts._db import SyncSession

_OUTPUT_FILE = "backfill_report.csv"
_CSV_FIELDNAMES = [
    "entry_id",
    "date",
    "legacy_diet_risk",
    "photo_derived_flags",
    "photos_only_flags",
    "manual_only_flags",
    "histamine_load",
    "fodmap_count",
    "gluten_count",
    "dairy_count",
]


def _parse_legacy_flags(diet_risk: str) -> set[str]:
    """Split comma-separated diet_risk string into a set of flag strings.

    Unlike parse_diet_risk_csv in app.services.diet_flags, this preserves all
    legacy tokens (including "normal" and unknown values) so the report shows
    exactly what was in the column.
    """
    if not diet_risk or diet_risk.strip().lower() == "normal":
        return set()
    return {f.strip() for f in diet_risk.split(",") if f.strip()}


def _load_entries(session: Session) -> list[Entry]:
    """Fetch all entries with their photo chain eagerly loaded."""
    result = session.execute(
        select(Entry)
        .options(
            selectinload(Entry.photos)
            .selectinload(Photo.analysis)
            .selectinload(PhotoAnalysis.ingredients)
        )
        .order_by(Entry.date)
    )
    return list(result.scalars().all())


def run() -> None:
    with SyncSession() as session:
        entries = _load_entries(session)

    n_total = len(entries)
    n_photos_only = 0
    n_manual_only = 0

    output_path = Path(_OUTPUT_FILE)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()

        for entry in entries:
            legacy_flags = _parse_legacy_flags(entry.diet_risk)
            signal = compute_photo_signal(entry)
            photo_flags = signal.flags

            photos_only = photo_flags - legacy_flags
            manual_only = legacy_flags - photo_flags

            if photos_only:
                n_photos_only += 1
            if manual_only:
                n_manual_only += 1

            writer.writerow(
                {
                    "entry_id": entry.id,
                    "date": entry.date.isoformat(),
                    "legacy_diet_risk": entry.diet_risk,
                    "photo_derived_flags": ",".join(sorted(photo_flags)),
                    "photos_only_flags": ",".join(sorted(photos_only)),
                    "manual_only_flags": ",".join(sorted(manual_only)),
                    "histamine_load": signal.scores.histamine_load,
                    "fodmap_count": signal.scores.fodmap_count,
                    "gluten_count": signal.scores.gluten_count,
                    "dairy_count": signal.scores.dairy_count,
                }
            )

    print(f"Report written to {output_path.resolve()}")
    print(
        f"{n_total} entries scanned; "
        f"{n_photos_only} have photos-only-flags; "
        f"{n_manual_only} have manual-only flags."
    )


if __name__ == "__main__":
    run()
