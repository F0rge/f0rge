"""Orchestrator: seed the dietary reference database in correct order."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import List

from scripts._db import SyncSession
from scripts.load_sighi import load as load_sighi
from scripts.load_fodmap import load as load_fodmap
from scripts.load_allergens import load as load_allergens
from scripts.build_aliases import load as load_aliases
from scripts.load_curated import load as load_curated

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
VALID_FODMAP_VALUES = ("low", "moderate", "high")


def verify_manifest() -> None:
    """Fail loudly if on-disk JSON checksums diverge from manifest.json."""
    manifest_path = _DATA_DIR / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing source manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", [])
    errors: List[str] = []

    for entry in files:
        filename = entry["filename"]
        expected = entry["sha256"]
        path = _DATA_DIR / filename
        if not path.exists():
            errors.append(f"Manifest entry missing on disk: {filename}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(
                f"Checksum mismatch for {filename}: expected {expected}, got {actual}"
            )

    if errors:
        for err in errors:
            log.error("MANIFEST FAILED: %s", err)
        raise RuntimeError(f"Source manifest verification failed ({len(errors)} error(s))")

    log.info("Manifest verified: %d source file(s) OK", len(files))


def validate_dietary_load() -> None:
    """Post-load sanity checks: row counts, score ranges, alias FK coverage."""
    errors: List[str] = []

    with SyncSession() as session:
        from sqlalchemy import text

        # --- Row counts ---
        ingredient_count = session.execute(
            text("SELECT COUNT(*) FROM dietary_ingredients")
        ).scalar_one()
        alias_count = session.execute(text("SELECT COUNT(*) FROM ingredient_aliases")).scalar_one()
        log.info(
            "Validation: %d dietary_ingredients, %d ingredient_aliases",
            ingredient_count,
            alias_count,
        )

        if ingredient_count == 0:
            errors.append("dietary_ingredients is empty after seed")
        if alias_count == 0:
            errors.append("ingredient_aliases is empty after seed")

        # --- Histamine scores: must be NULL or 0-3 ---
        bad_histamine = session.execute(
            text(
                "SELECT canonical_name, histamine_score FROM dietary_ingredients "
                "WHERE histamine_score IS NOT NULL AND histamine_score NOT IN (0, 1, 2, 3)"
            )
        ).fetchall()
        if bad_histamine:
            for row in bad_histamine:
                errors.append(f"Out-of-range histamine_score {row[1]} on '{row[0]}'")

        # --- FODMAP values: must be NULL or one of low/moderate/high ---
        fodmap_cols = ("fodmap_oligos", "fodmap_fructose", "fodmap_polyols", "fodmap_lactose")
        fodmap_in = ", ".join(f"'{v}'" for v in VALID_FODMAP_VALUES)
        for col in fodmap_cols:
            bad_fodmap = session.execute(
                text(
                    f"SELECT canonical_name, {col} FROM dietary_ingredients "
                    f"WHERE {col} IS NOT NULL AND {col} NOT IN ({fodmap_in})"
                )
            ).fetchall()
            if bad_fodmap:
                for row in bad_fodmap:
                    errors.append(f"Invalid {col} value '{row[1]}' on '{row[0]}'")

        # --- Alias FK coverage: no orphaned aliases ---
        orphaned = session.execute(
            text(
                "SELECT ia.alias, ia.canonical_name FROM ingredient_aliases ia "
                "LEFT JOIN dietary_ingredients di ON ia.canonical_name = di.canonical_name "
                "WHERE di.canonical_name IS NULL"
            )
        ).fetchall()
        if orphaned:
            for row in orphaned:
                errors.append(f"Orphaned alias '{row[0]}' → missing canonical '{row[1]}'")

    if errors:
        for err in errors:
            log.error("VALIDATION FAILED: %s", err)
        raise RuntimeError(f"Post-load validation failed with {len(errors)} error(s)")

    log.info("Validation passed: all checks OK")


def main() -> None:
    start = time.monotonic()
    log.info("=== Starting dietary database seed ===")

    log.info("--- Manifest verification ---")
    verify_manifest()

    log.info("--- Step 1/5: SIGHI histamine data ---")
    load_sighi()

    log.info("--- Step 2/5: FODMAP data ---")
    load_fodmap()

    log.info("--- Step 3/5: Allergen flags ---")
    load_allergens()

    log.info("--- Step 4/5: Ingredient aliases ---")
    load_aliases()

    # Runs after build_aliases so its aliases survive that table rebuild.
    log.info("--- Step 5/5: Curated ingredients + aliases ---")
    load_curated()

    log.info("--- Validation ---")
    validate_dietary_load()

    elapsed = time.monotonic() - start
    log.info("=== Dietary database seed complete in %.1fs ===", elapsed)


if __name__ == "__main__":
    main()
