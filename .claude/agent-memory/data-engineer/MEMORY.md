# Data Engineer Memory

## Dietary Database Sources

| Source | URL | Format | Status |
|--------|-----|--------|--------|
| SIGHI Histamine List | histaminintoleranz.ch/en/downloads.html | PDF | Needs ETL script |
| fodmap_list | github.com/oseparovic/fodmap_list | JSON | Ready to ingest |
| Open Food Facts | openfoodfacts.github.io | REST API (no auth) | On-demand lookups |
| Histaminer | histaminer.com | Web (SIGHI search) | Reference only |

## Target SQLite Schema

Tables to create in health.db:
- **ingredients** — canonical ingredient list (id, name, category)
- **ingredient_aliases** — synonym/alias mappings (id, ingredient_id FK, alias, language)
- **histamine_scores** — SIGHI data (ingredient_id FK, score 0-3, notes)
- **fodmap_scores** — FODMAP data (ingredient_id FK, oligos, fructose, polyols, lactose levels)
- **allergen_flags** — binary flags (ingredient_id FK, contains_gluten, contains_dairy)

## ETL Scripts Needed

All in `backend/scripts/`, run via `uv run python -m scripts.<name>`:
1. `etl_sighi.py` — Parse SIGHI PDF into ingredients + histamine_scores
2. `etl_fodmap.py` — Ingest fodmap_list JSON into ingredients + fodmap_scores
3. `etl_openfoodfacts.py` — Batch query Open Food Facts for allergen data
4. `build_aliases.py` — Build synonym/alias table from all sources
5. `seed_dietary_db.py` — Orchestrator: runs all ETL in order, reports summary

## Conventions

- All scripts idempotent (safe to re-run, UPSERT pattern)
- Source data versioned (download date, URL, checksum stored)
- Validation after each load (row counts, null checks, score ranges 0-3)
- `from __future__ import annotations` in all files
- Python 3.10 compatible
- SQLite-safe (no PostgreSQL features)

## Database Details

- Path: backend/data/health.db
- Engine: sync SQLAlchemy with SQLite
- Existing models in app/models/ — new dietary tables follow same patterns
- No Alembic — manual migration in main.py _run_migrations()
