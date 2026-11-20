> Canonical decisions: [`docs/adr/README.md`](../../docs/adr/README.md). Follow [P-005](../../docs/adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../docs/adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# apps/environment-monitor

Room sensor dashboard (temperature and humidity). App `envmon`: two Coolify applications on the Pi that run the Artifacts CI builds. Source import of `leothesouthafrican/environment-monitor` `cursor/primer-theme-266b` at `39afb06a0cc603f3aaa4bb692041f0ebe8fa82f5`.

## Data safety

- SQLite file is `/app/data/readings.db` (WAL). Filename and directory stay as they are.
- Docker volume name is `environment-monitor_sensor_data`, mounted at `/app/data`. The nightly backup tars that volume by name (`backup-sensor-data.sh`). Do not rename the volume, the mount, or the compose service volume key.
- Do not add a compose file or a volume `name:` that would create a different volume. Coolify keeps the existing storage. `docker-compose.yml` is the imported file; its project directory basename must stay `environment-monitor` so the implicit volume name stays `environment-monitor_sensor_data`.
- Do not change schema, migration, or startup logic in `backend/services/sensor_service.py` or `backend/migrate_to_sqlite.py`.
- Ports stay backend `5001` and frontend `5000`.
- Env var names stay `BACKEND_URL` (frontend) and `PYTHONUNBUFFERED` (both).
- This repo is public. Never commit `*.db`, `*.csv`, `data/`, or `.env`.

## Release

Nx projects `environment-monitor-backend` and `environment-monitor-frontend` are Coolify "Docker image" applications with the same names. A reviewed merge to `main` that affects either releases both through [the pipeline](../../.github/deploy/README.md). The backend application keeps the data volume at `/app/data` through a Coolify Persistent Storage directory mount; Coolify ignores `-v` in Custom Docker Options. It also carries the network alias `em-backend`, which the frontend's nginx proxies to over the shared `coolify` network. Each Dockerfile's build context is its own app directory, not the repo root.

## Checks

- `python3 test_aggregation.py` in `backend/` (stdlib only; hardware imports are stubbed).
- `npm ci && npm run build` in `frontend/`. The frontend is not an npm workspace; root React 19 overrides must not apply.
- Image dependencies stay in `backend/requirements.txt`. Do not switch the Dockerfile to `uv sync`.
