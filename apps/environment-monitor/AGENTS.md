# apps/environment-monitor

Room sensor dashboard (temperature and humidity). Two Coolify apps on the Pi, Dockerfiles built from `F0rge/f0rge` `main`. Source import of `leothesouthafrican/environment-monitor` `cursor/primer-theme-266b` at `39afb06a0cc603f3aaa4bb692041f0ebe8fa82f5`.

## Data safety

- SQLite file is `/app/data/readings.db` (WAL). Filename and directory stay as they are.
- Docker volume name is `environment-monitor_sensor_data`, mounted at `/app/data`. The nightly backup tars that volume by name (`backup-sensor-data.sh`). Do not rename the volume, the mount, or the compose service volume key.
- Do not add a compose file or a volume `name:` that would create a different volume. Coolify keeps the existing storage. `docker-compose.yml` is the imported file; its project directory basename must stay `environment-monitor` so the implicit volume name stays `environment-monitor_sensor_data`.
- Do not change schema, migration, or startup logic in `backend/services/sensor_service.py` or `backend/migrate_to_sqlite.py`.
- Ports stay backend `5001` and frontend `5000`.
- Env var names stay `BACKEND_URL` (frontend) and `PYTHONUNBUFFERED` (both).
- This repo is public. Never commit `*.db`, `*.csv`, `data/`, or `.env`.

## Deploy

| App | Nx project | Coolify UUID | Actions secret |
|-----|------------|--------------|----------------|
| Backend | `environment-monitor-backend` | `x408g80c0cggs4okgok4cc0o` | `COOLIFY_WEBHOOK_ENVMON_BACKEND` |
| Frontend | `environment-monitor-frontend` | `zk8s00gk0g88cc08gkswkc44` | `COOLIFY_WEBHOOK_ENVMON_FRONTEND` |

Coolify base directory is the app directory (`apps/environment-monitor/backend` or `.../frontend`), Dockerfile `Dockerfile`, watch path `apps/environment-monitor/backend/**` or `.../frontend/**`. Build context is that directory, not the repo root. Manifest entries omit `health_url` (Pi is not reachable from GitHub runners).

## Checks

- `python3 test_aggregation.py` in `backend/` (stdlib only; hardware imports are stubbed).
- `npm ci && npm run build` in `frontend/`. The frontend is not an npm workspace; root React 19 overrides must not apply.
- Image dependencies stay in `backend/requirements.txt`. Do not switch the Dockerfile to `uv sync`.
