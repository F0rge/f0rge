# FastAPI Backend Memory

## Project Structure

- Routers: auth, entries, enriched, health_metrics, photos, weather
- Services: obsidian, health_import, photo_storage, weather
- Models: entry, health_metrics, session, photo, weather
- Schemas: auth, entry, enriched, health_metrics, photo, weather
- No `app/dependencies/` dir yet — services instantiated directly in routers (needs refactoring)

## Endpoints

| Router | Endpoints |
|--------|-----------|
| auth | POST login, POST logout, GET me |
| entries | POST/GET/PUT/DELETE /entries, GET /entries?month=YYYY-MM |
| photos | POST /entries/{date}/photos, GET /photos/{id}/file, DELETE /photos/{id} |
| health_metrics | POST /health-metrics/import (Bearer+session), GET /health-metrics/{date} |
| weather | POST /weather/fetch, GET /weather/{date} |
| enriched | GET /enriched/{date} (combines entry+weather+health_metrics) |

## Database

- Sync SQLAlchemy + SQLite (backend/data/health.db)
- get_db() in database.py yields SessionLocal
- No Alembic — manual _run_migrations() in main.py (ALTER TABLE for missing columns)
- create_all() on startup via lifespan hook

## Models

- **entries**: id, date(unique), overall, bloating, stool_normal, stool_type, joint_pain, neuro, sleep_quality, stress, diet_risk, supplements, sick, notes, created_at, updated_at
- **photos**: id, entry_id(FK), filename, label, original_filename, created_at — cascade delete
- **health_metrics**: id, date(unique+indexed), hrv_mean/std, resting_hr, sleep_hours/deep/rem/core/awake, sleep_efficiency, steps, active_minutes, spo2, wrist_temp_deviation, source
- **auth_sessions**: id, token(unique+indexed), created_at, expires_at

## Auth Pattern

- PIN login: bcrypt.checkpw against config pin_hash
- 90-day session tokens (hex(32)) stored in auth_sessions
- ht_session cookie (httponly, samesite=lax)
- get_current_session() middleware validates cookie + expiry
- health_metrics/import also accepts Bearer token

## Config (app/config.py)

Settings via pydantic-settings: pin_hash, vault_path, database_url, secret_key, cors_origins, photo_dir, openweathermap_api_key/city, weather_fetch_enabled, health_import_token

## Dependencies (pyproject.toml)

fastapi[standard], sqlalchemy>=2.0, pydantic-settings>=2.0, bcrypt>=4.0, pillow>=10.0, python-multipart, httpx>=0.27

## Known Technical Debt

- Business logic in routers (needs refactoring to service layer)
- No dependencies/ directory for Depends() factories
- No test files exist yet
- Manual migrations instead of Alembic
