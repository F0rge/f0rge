# FastAPI Backend Memory

## Project Stack

- FastAPI + sync SQLAlchemy + SQLite (Python 3.10 target)
- API prefix: `/api/v1`
- Auth: PIN-based session cookies (`ht_session`, httponly, 90-day TTL)
- Package manager: `uv` (never `pip`)
- Lint/format: `ruff`
- `from __future__ import annotations` in every Python file
- No Alembic — manual `_run_migrations()` in `main.py` (ALTER TABLE pattern; SQLite-safe)
- `app/dependencies/` directory holds `Depends()` factories (introduced for food-analysis)

## Layout

- `app/routers/` — auth, entries, photos, weather, health_metrics, enriched, food_analysis, supplement_catalog, treatments, export
- `app/services/` — obsidian, photo_storage, weather, food_analysis, ingredient_lookup, vision_prompt, feature_matrix, photos, treatments
- `app/models/` — entry, photo, photo_analysis, photo_ingredient, dietary_ingredient, ingredient_alias, session, health_metrics, weather, supplement_catalog
- `app/schemas/` — Pydantic v2, `Create`/`Update`/`Response` naming
- `app/dependencies/` — `get_food_analysis_service`, `get_ingredient_lookup_service`, `get_photo_service`

## Lessons learned (patterns that bit us in production)

### SQLite NOT NULL is immutable via ALTER COLUMN
Declaring `nullable=True` on a model **doesn't change an existing prod table column** — SQLite can't drop NOT NULL without a full table rebuild. When migrating a model field to nullable, you must either: (a) backfill at the API/service layer (e.g., derive `stool_normal` from `stool_status` before writing); or (b) write a table-rebuild migration (CREATE new + INSERT SELECT + DROP + RENAME). `Base.metadata.create_all()` never touches existing tables.
*Why:* PR #5 was a full prod outage — model said nullable, prod said NOT NULL, every entry save returned 500.

### 1:1 relationship with NOT NULL FK on the child needs cascade
When defining `Parent.child = relationship(Child, uselist=False)` and `Child.parent_id` is `NOT NULL`, SQLAlchemy will try to NULL the FK on delete instead of deleting the child row — the commit blows up with IntegrityError. Always add `cascade="all, delete-orphan", single_parent=True` on the parent's side. Test by deleting a parent that has a child attached.
*Why:* PR #8 prod outage on photo delete — `Photo.analysis` was missing cascade.

### Feature flag + external cred must not BOTH default to "active"
A feature flag that defaults `True` while its required credential defaults `""` is a footgun. The first deploy that forgets the env var will silently crash on every request. Either: (a) default the flag `False`; (b) gate the active path on `flag AND cred` (not just `flag`); (c) emit a startup WARNING when misconfigured. Ideally all three.
*Why:* PR #7 prod outage — `FOOD_ANALYSIS_ENABLED=true` + empty `OPENROUTER_API_KEY` crashed httpx on `Bearer ` (empty) header every upload.

### "Next number" sequences: MAX(n)+1, not COUNT()+1
For any numbering scheme that needs uniqueness across the lifetime of a record (filenames, slugs, ordinals), parse `MAX(existing)+1` from the actual values — `COUNT()+1` is wrong as soon as any row is deleted. Two rows can end up with the same generated value.
*Why:* PR #16 — critical silent data corruption found by QA exploratory test. After deleting `_photo-1.jpg`, the next upload got `_photo-2.jpg` colliding with the existing photo 2.

### Order destructive operations: DB commit first, filesystem second
DB transactions roll back, filesystem operations don't. If you `os.unlink(file)` before `db.commit()` and the commit fails, you end up with orphan DB rows pointing at missing files. Always commit DB writes first; on success, do the filesystem cleanup; on rollback, the filesystem is untouched.
*Why:* `photos.py` DELETE was deleting files before commit. When the cascade bug (#8) caused IntegrityError, files were already gone but the row remained — orphan state.

### FastAPI Form defaults break direct-call tests
When a router function uses `param: Optional[X] = Form(None)`, calling the coroutine directly in tests (bypassing FastAPI's form parsing) passes `Form(None)` — the sentinel object — as the value, not `None`. SQLAlchemy then tries to persist `Form(None)` and blows up with a type error. Fix: always pass all new Form params explicitly in test helper calls (e.g., `meal_time=None`). Affects any test that calls a router coroutine directly rather than through `TestClient`.
*Why:* Phase 1 (issue #35) — adding `meal_time: Optional[datetime] = Form(None)` to `upload_photo` broke all existing `test_photo_filename.py` tests that called the coroutine directly without specifying `meal_time`.
