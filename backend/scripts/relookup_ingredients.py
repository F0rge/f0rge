"""Re-run dietary lookup on photo ingredients that have no canonical match.

Usage:
    cd backend && uv run python -m scripts.relookup_ingredients [--dry-run]

Finds every PhotoIngredient where canonical_name IS NULL, re-runs the
IngredientLookupService, and updates the dietary flags if a match is found.
Then re-renders affected Obsidian vault files.
"""
from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.entry import Entry
from app.models.photo import Photo
from app.models.photo_analysis import PhotoAnalysis
from app.models.photo_ingredient import PhotoIngredient
from app.services.ingredient_lookup import IngredientLookupService
from app.services.obsidian import write_daily_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-lookup unmatched ingredients")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db: Session = SessionLocal()

    unmatched = (
        db.query(PhotoIngredient)
        .filter(PhotoIngredient.canonical_name.is_(None))
        .all()
    )

    if not unmatched:
        print("All ingredients already matched. Nothing to do.")
        db.close()
        return

    print(f"Found {len(unmatched)} unmatched ingredient(s). Running lookup...\n")

    lookup = IngredientLookupService(db)
    resolved = 0
    still_missing = 0
    affected_analysis_ids: set[int] = set()

    for ing in unmatched:
        match = lookup.lookup(ing.name)
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
                affected_analysis_ids.add(ing.analysis_id)
                print(f"  {ing.name} -> {match.canonical_name} (H:{match.histamine_score})")
            resolved += 1
        else:
            print(f"  {ing.name} -> ? (still no match)")
            still_missing += 1

    if args.dry_run:
        print(f"\n--dry-run: {resolved} would be resolved, {still_missing} still missing.")
        db.close()
        return

    db.commit()

    affected_analyses = (
        db.query(PhotoAnalysis)
        .filter(PhotoAnalysis.id.in_(list(affected_analysis_ids)))
        .all()
    )
    photo_ids = [a.photo_id for a in affected_analyses]
    photos = db.query(Photo).filter(Photo.id.in_(photo_ids)).all()
    entry_ids = set(p.entry_id for p in photos)
    entries = db.query(Entry).filter(Entry.id.in_(list(entry_ids))).all()

    print(f"\nRe-rendering {len(entries)} vault file(s)...")
    for entry in entries:
        db.refresh(entry)
        write_daily_file(db, entry, entry.photos)
        print(f"  {entry.date.isoformat()}")

    db.close()
    print(f"\nDone. Resolved {resolved}, still missing {still_missing}.")


if __name__ == "__main__":
    main()
