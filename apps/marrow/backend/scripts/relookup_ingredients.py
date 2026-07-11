"""Re-run dietary lookup on photo ingredients that have no canonical match.

Usage:
    cd backend && uv run python -m scripts.relookup_ingredients [--dry-run]

Finds every PhotoIngredient where canonical_name IS NULL, re-runs the
sync lookup (mirroring refresh_ingredient_lookup._lookup_sync), and
updates the dietary flags if a match is found.

Vault markdown files are NOT re-rendered by this script — affected
entries' photo_signal updates on the next API read.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

import app.models  # noqa: F401 - registers ORM classes with Base.metadata
from app.models.photo_ingredient import PhotoIngredient
from scripts._db import SyncSession
from scripts.refresh_ingredient_lookup import _lookup_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-lookup unmatched ingredients")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SyncSession() as session:
        unmatched = (
            session.execute(select(PhotoIngredient).where(PhotoIngredient.canonical_name.is_(None)))
            .scalars()
            .all()
        )

        if not unmatched:
            print("All ingredients already matched. Nothing to do.")
            return

        print(f"Found {len(unmatched)} unmatched ingredient(s). Running lookup...\n")

        resolved = 0
        still_missing = 0

        for ing in unmatched:
            match = _lookup_sync(session, ing.name)
            if match:
                if args.dry_run:
                    print(f"  {ing.name} -> {match.canonical_name} (H:{match.histamine_score})")
                else:
                    ing.canonical_name = match.canonical_name
                    ing.histamine_score = match.histamine_score
                    ing.fodmap_oligos = match.fodmap_oligos
                    ing.fodmap_fructose = match.fodmap_fructose
                    ing.fodmap_polyols = match.fodmap_polyols
                    ing.fodmap_lactose = match.fodmap_lactose
                    ing.contains_gluten = match.contains_gluten
                    ing.contains_dairy = match.contains_dairy
                    print(f"  {ing.name} -> {match.canonical_name} (H:{match.histamine_score})")
                resolved += 1
            else:
                print(f"  {ing.name} -> ? (still no match)")
                still_missing += 1

        if args.dry_run:
            print(f"\n--dry-run: {resolved} would be resolved, {still_missing} still missing.")
            return

        session.commit()

    print(
        f"\nDone. Resolved {resolved}, still missing {still_missing}."
        "\nNote: entry photo_signal updates on next API read."
    )


if __name__ == "__main__":
    main()
