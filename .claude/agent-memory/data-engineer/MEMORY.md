# Data Engineer Memory

## Dietary Reference Tables

| Table | Source | Schema highlights |
|-------|--------|-------------------|
| `dietary_ingredients` | SIGHI + FODMAP + allergens | canonical_name (unique), category, histamine_score (0-3), fodmap_* (low/moderate/high), contains_gluten/dairy (bool) |
| `ingredient_aliases` | `build_aliases.py` | alias, canonical_name (FK), language |

Current counts (as of last seed): ~317 canonicals, 409 aliases.

## ETL Scripts (`backend/scripts/`)

- `load_sighi.py` — SIGHI histamine, ~285 ingredients
- `load_fodmap.py` — FODMAP levels, ~160 ingredients
- `load_allergens.py` — gluten/dairy flags, ~110 ingredients
- `build_aliases.py` — synonym table (EN + FR + DE translations), plurals, qualifier variants
- `seed_dietary_db.py` — orchestrator, runs all 4 in order
- `_paths.py` — `data_dir()` helper, reads `DIETARY_DATA_DIR` env var or falls back to `backend/data/`

Idempotent — safe to re-run. INSERT OR REPLACE pattern.

## Database

- Sync SQLAlchemy + SQLite
- Path: `backend/data/health.db` (local dev) or `/app/data/health.db` (prod, volume-mounted)
- `Base.metadata.create_all()` on startup creates tables but does NOT seed them
- Lifespan hook `_seed_dietary_db_if_empty()` runs `seed_dietary_db` automatically on first boot

## Dockerfile

The image must include:
- `COPY ./scripts ./scripts` — loaders accessible at `/app/scripts/`
- `COPY ./data /app/data-seed` — JSON files **outside** the volume-mounted `/app/data/` path
- `ENV DIETARY_DATA_DIR=/app/data-seed` — so loaders find the JSON files

The `/app/data/` path is a Docker volume (`health-tracker-data`) at runtime — anything COPY'd there is shadowed.

## Conventions

- `from __future__ import annotations` at the top of every Python file
- Python 3.10 compatible
- All scripts use plain `sqlite3` (not SQLAlchemy ORM) — simpler, no app context needed
- INSERT OR REPLACE on canonical_name for idempotency
- Source traceability: each row records `source` ("sighi", "fodmap_list", "manual") and `source_version`
