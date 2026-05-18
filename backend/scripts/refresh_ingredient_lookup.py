"""Post-audit deployment helper for the ingredient lookup data.

Three independent steps, each gated by a flag so you can run them in isolation
or combine. All destructive operations support --dry-run.

  --load             Repopulate the DietaryIngredient table from the three
                     JSON files (sighi_histamine, fodmap_list, allergens).
                     Calls the existing load_* scripts. Idempotent UPSERT.

  --prune-orphans    Delete DietaryIngredient rows whose canonical_name no
                     longer appears in any JSON file. Catches compound
                     dishes and other entries removed by the audit.

  --rescore-photos   Re-run dietary lookup for every existing PhotoIngredient
                     row (except user_edited=True) and update its dietary
                     flags in place. Past PhotoIngredient rows store their
                     values at insert time and are otherwise frozen.

  --all              Shorthand for --load --prune-orphans --rescore-photos.

  --dry-run          Preview without writing. Honored by all destructive steps.

Usage:
    cd backend && uv run python -m scripts.refresh_ingredient_lookup --dry-run --all
    cd backend && uv run python -m scripts.refresh_ingredient_lookup --load --prune-orphans
    cd backend && uv run python -m scripts.refresh_ingredient_lookup --rescore-photos

Vault markdown files are NOT re-rendered by this script — past entries'
photo_signal updates on next entry read; vault files stay stale until a
re-render is triggered separately. (Acceptable: vault re-renders only fire
on photo confirm events, not on entry reads.)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers ORM classes with Base.metadata
from app.models.dietary_ingredient import DietaryIngredient
from app.models.ingredient_alias import IngredientAlias
from app.models.photo_ingredient import PhotoIngredient
from scripts._db import SyncSession
from scripts._paths import data_dir
from scripts.load_allergens import load as load_allergens
from scripts.load_fodmap import load as load_fodmap
from scripts.load_sighi import load as load_sighi

# Mirrors of the guards in app.services.ingredient_lookup so plant milks /
# nut butters do not fall through to "milk" / "butter".
_PLANT_QUALIFIERS = frozenset(
    {
        "coconut",
        "oat",
        "almond",
        "soy",
        "soya",
        "rice",
        "cashew",
        "hemp",
        "peanut",
        "hazelnut",
        "macadamia",
        "pistachio",
        "sunflower",
        "flax",
        "walnut",
        "pecan",
        "sesame",
        "cocoa",
    }
)
_DAIRY_HEAD_NOUNS = frozenset(
    {"milk", "cream", "butter", "cheese", "yogurt", "yoghurt", "kefir"}
)

_DIETARY_FIELDS = (
    "canonical_name",
    "histamine_score",
    "fodmap_oligos",
    "fodmap_fructose",
    "fodmap_polyols",
    "fodmap_lactose",
    "contains_gluten",
    "contains_dairy",
)


def _lookup_sync(session: Session, name: str) -> Optional[DietaryIngredient]:
    """Sync mirror of app.services.ingredient_lookup.IngredientLookupService.lookup.

    Kept in lockstep with that service. If the production lookup chain
    changes, update this helper too.
    """
    normalised = name.lower().strip()
    if not normalised:
        return None

    # 1. Exact canonical match
    row = session.execute(
        select(DietaryIngredient).where(DietaryIngredient.canonical_name == normalised)
    ).scalar_one_or_none()
    if row:
        return row

    # 2. Alias lookup
    alias = session.execute(
        select(IngredientAlias).where(IngredientAlias.alias == normalised)
    ).scalar_one_or_none()
    if alias:
        return session.execute(
            select(DietaryIngredient).where(
                DietaryIngredient.canonical_name == alias.canonical_name
            )
        ).scalar_one_or_none()

    # 3. Head-noun fallback
    words = normalised.split()
    if len(words) > 1:
        last_word = words[-1]
        qualifiers = set(words[:-1])
        if not (last_word in _DAIRY_HEAD_NOUNS and qualifiers & _PLANT_QUALIFIERS):
            row = session.execute(
                select(DietaryIngredient).where(
                    DietaryIngredient.canonical_name == last_word
                )
            ).scalar_one_or_none()
            if row:
                return row
            alias = session.execute(
                select(IngredientAlias).where(IngredientAlias.alias == last_word)
            ).scalar_one_or_none()
            if alias:
                return session.execute(
                    select(DietaryIngredient).where(
                        DietaryIngredient.canonical_name == alias.canonical_name
                    )
                ).scalar_one_or_none()

    # 4. Case-insensitive LIKE substring (shortest match wins)
    return (
        session.execute(
            select(DietaryIngredient)
            .where(DietaryIngredient.canonical_name.ilike(f"%{normalised}%"))
            .order_by(func.length(DietaryIngredient.canonical_name))
        )
        .scalars()
        .first()
    )


def step_load() -> None:
    print("=== Step: --load — repopulate DietaryIngredient from JSON ===")
    load_sighi()
    load_fodmap()
    load_allergens()


def _collect_json_names() -> set[str]:
    names: set[str] = set()
    for filename in ("sighi_histamine.json", "fodmap_list.json", "allergens.json"):
        for item in json.load(open(data_dir() / filename)):
            names.add(item["name"].strip().lower())
    return names


def step_prune_orphans(dry_run: bool) -> None:
    print("=== Step: --prune-orphans — drop DB rows not in any JSON ===")
    json_names = _collect_json_names()

    with SyncSession() as session:
        all_rows = session.execute(select(DietaryIngredient)).scalars().all()
        orphans = [r for r in all_rows if r.canonical_name not in json_names]

        if not orphans:
            print("No orphans found.")
            return

        print(f"Found {len(orphans)} orphan(s):")
        for r in orphans:
            print(f"  - {r.canonical_name}")

        orphan_names = [r.canonical_name for r in orphans]
        alias_count = session.execute(
            select(func.count())
            .select_from(IngredientAlias)
            .where(IngredientAlias.canonical_name.in_(orphan_names))
        ).scalar_one()
        if alias_count:
            print(
                f"  ({alias_count} alias row(s) point to these — will be deleted first.)"
            )

        if dry_run:
            print("--dry-run: no rows deleted.")
            return

        # Cascade aliases first; FK constraint blocks parent deletion otherwise.
        if alias_count:
            session.execute(
                delete(IngredientAlias).where(
                    IngredientAlias.canonical_name.in_(orphan_names)
                )
            )
        for r in orphans:
            session.delete(r)
        session.commit()
        print(
            f"Deleted {len(orphans)} orphan row(s) "
            f"(+ {alias_count} dependent alias row(s))."
        )


def step_rescore_photos(dry_run: bool) -> None:
    print("=== Step: --rescore-photos — refresh dietary flags on PhotoIngredient ===")

    with SyncSession() as session:
        rows = (
            session.execute(
                select(PhotoIngredient).where(
                    (PhotoIngredient.user_edited.is_(False))
                    | (PhotoIngredient.user_edited.is_(None))
                )
            )
            .scalars()
            .all()
        )

        if not rows:
            print("No eligible rows.")
            return

        print(
            f"Scanning {len(rows)} PhotoIngredient row(s) (user_edited rows skipped)."
        )

        changed = unchanged = unmatched = 0
        for ing in rows:
            match = _lookup_sync(session, ing.name)
            if match is None:
                unmatched += 1
                continue

            new_values = {f: getattr(match, f) for f in _DIETARY_FIELDS}
            current = {f: getattr(ing, f) for f in _DIETARY_FIELDS}
            if current == new_values:
                unchanged += 1
                continue

            changed += 1
            if dry_run:
                print(
                    f"  id={ing.id} {ing.name!r}: "
                    f"H {current['histamine_score']} -> {new_values['histamine_score']}, "
                    f"gluten {current['contains_gluten']} -> {new_values['contains_gluten']}, "
                    f"dairy {current['contains_dairy']} -> {new_values['contains_dairy']}"
                )
            else:
                for f, v in new_values.items():
                    setattr(ing, f, v)

        if dry_run:
            print(
                f"--dry-run: would change {changed} row(s); "
                f"{unchanged} unchanged; {unmatched} unmatched."
            )
            return

        session.commit()
        print(
            f"Updated {changed} row(s); {unchanged} unchanged; {unmatched} unmatched."
        )
        print(
            "Note: vault markdown files were NOT re-rendered. Past entries' "
            "photo_signal will update on next API read; vault files stay stale."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh ingredient lookup data after JSON audit changes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--load", action="store_true", help="Reload JSON into DB")
    parser.add_argument(
        "--prune-orphans",
        action="store_true",
        help="Delete DB rows not in any JSON file",
    )
    parser.add_argument(
        "--rescore-photos",
        action="store_true",
        help="Refresh dietary flags on existing PhotoIngredient rows",
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all three steps in order"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    if args.all:
        args.load = True
        args.prune_orphans = True
        args.rescore_photos = True

    if not (args.load or args.prune_orphans or args.rescore_photos):
        parser.print_help()
        sys.exit(1)

    if args.load:
        if args.dry_run:
            print("--load does not support --dry-run; skipping. (The underlying")
            print("load_* scripts always upsert.)")
            print()
        else:
            step_load()
            print()
    if args.prune_orphans:
        step_prune_orphans(args.dry_run)
        print()
    if args.rescore_photos:
        step_rescore_photos(args.dry_run)


if __name__ == "__main__":
    main()
