#!/usr/bin/env bash
# Dump Fly MPG (marrow / marrow_dev) and restore into Railway Postgres.
# Prerequisites: flyctl auth, psql/pg_dump/pg_restore, Railway DATABASE_PUBLIC_URL.
#
# Usage:
#   ./apps/marrow/backend/scripts/railway_pg_migrate.sh develop
#   ./apps/marrow/backend/scripts/railway_pg_migrate.sh production
set -euo pipefail

ENV="${1:?usage: $0 develop|production}"
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${ROOT}/.tmp/railway-pg-migrate"
mkdir -p "$OUT_DIR"

case "$ENV" in
  develop)
    FLY_DB="marrow_dev"
    DUMP="$OUT_DIR/marrow_dev_${STAMP}.dump"
    ;;
  production)
    FLY_DB="marrow"
    DUMP="$OUT_DIR/marrow_${STAMP}.dump"
    ;;
  *)
    echo "ENV must be develop or production" >&2
    exit 1
    ;;
esac

: "${RAILWAY_DATABASE_URL:?Set RAILWAY_DATABASE_URL to the target public Postgres URL}"

echo "==> Dumping Fly MPG database $FLY_DB"
# Prefer fly mpg proxy or attached DATABASE_URL. Override FLY_DATABASE_URL if needed.
: "${FLY_DATABASE_URL:?Set FLY_DATABASE_URL to a Fly MPG connection string for $FLY_DB}"

pg_dump -Fc --no-acl --no-owner -d "$FLY_DATABASE_URL" -f "$DUMP"
echo "Wrote $DUMP"

echo "==> Restoring into Railway (drops existing objects in public schema first is NOT done — use empty DB)"
pg_restore --no-acl --no-owner -d "$RAILWAY_DATABASE_URL" "$DUMP" || {
  echo "pg_restore exited non-zero (often OK for extension/role notices). Inspect carefully." >&2
}

echo "==> Verify"
psql "$RAILWAY_DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
psql "$RAILWAY_DATABASE_URL" -c "SELECT COUNT(*) AS alembic_rows FROM alembic_version;"

echo "Done. Next: run railway_bootstrap_roles.sql if roles missing, then wire DATABASE_URL / MIGRATION_DATABASE_URL."
