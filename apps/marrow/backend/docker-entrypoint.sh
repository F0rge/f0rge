#!/bin/sh
# Container entrypoint for the health-tracker backend image.
#
# The same image is used by three services (backend, mcp-server,
# embedding-worker). Only the backend should run Alembic on boot, otherwise
# three containers race to take the same DDL locks at every deploy. Opt-in
# via RUN_MIGRATIONS=1 on the service that owns migrations.
#
# When RUN_MIGRATIONS is unset / "0" / "false", the entrypoint is a no-op
# wrapper: it just exec's whatever CMD the compose file supplied (so
# mcp-server and embedding-worker behave exactly as before).
set -e

case "${RUN_MIGRATIONS:-0}" in
    1|true|TRUE|True|yes|YES)
        echo "[entrypoint] RUN_MIGRATIONS=${RUN_MIGRATIONS} — running alembic upgrade head"
        MIG_URL="${MIGRATION_DATABASE_URL:-$DATABASE_URL}"
        DATABASE_URL="$MIG_URL" uv run alembic upgrade head
        echo "[entrypoint] alembic upgrade complete"
        ;;
    *)
        echo "[entrypoint] RUN_MIGRATIONS unset — skipping alembic"
        ;;
esac

# If the caller passed a command, exec it. Otherwise fall back to uvicorn
# (matches the historical CMD so `docker run` without args still boots the API).
if [ "$#" -gt 0 ]; then
    exec "$@"
else
    exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
