---
name: Dev server startup for QA
description: How to start backend+frontend for browser smoke tests; handles stale-server-already-running
type: project
---

To launch both services for an e2e gate run:

```bash
cd /Users/leo/development/health-tracker/backend && uv run uvicorn app.main:app --port 8000
cd /Users/leo/development/health-tracker/frontend && PORT=3000 npm run dev
```

Both via `run_in_background`. Then poll readiness:
```bash
until curl -sf http://localhost:8000/api/v1/health; do sleep 1; done
until curl -sf http://localhost:3000; do sleep 1; done
```

**Watch for stale servers**: a prior session may have left dev servers running. Symptoms: the `run_in_background` task reports `failed` (port in use) but `curl` succeeds anyway. Check `ps aux | grep -E '(uvicorn|next dev|npm run dev)'`. If found and the running backend is **older than this PR**, kill and restart — otherwise migrations in this PR won't have run, and the database will be missing the new columns (e.g. `alcohol_units`). Diagnose via `sqlite3 backend/data/health.db "PRAGMA table_info(entries);"`.

The backend SIGTERM exit code is 144 when killed, which is expected; the background-task `failed` notifications can be ignored.

**Why:** caught a real bug during the meal_time/alcohol PR — stale uvicorn from a previous run meant the migration never executed, and the first DB queries blew up with "no such column: alcohol_units".

**How to apply:** before any e2e phase, verify the migration columns exist in the live DB. If not, restart the backend explicitly.
