#!/usr/bin/env bash
# Migrate dev Fly MPG data (fly-db on dev cluster) → health_dev on prod cluster.
#
# Prerequisites: flyctl, docker (postgres:16 image), FLY_API_TOKEN, fly mpg proxy.
#
# Usage:
#   ./scripts/fly-mpg-consolidate-dev.sh --dry-run     # counts only
#   ./scripts/fly-mpg-consolidate-dev.sh --execute     # dump, restore, grants
#
set -euo pipefail

DEV_CLUSTER="${DEV_CLUSTER:-d1zj5omzqg9ryqkv}"
PROD_CLUSTER="${PROD_CLUSTER:-z23750v13yl096d1}"
SOURCE_DB="${SOURCE_DB:-fly-db}"
TARGET_DB="${TARGET_DB:-health_dev}"
DEV_PROXY_PORT="${DEV_PROXY_PORT:-16381}"
PROD_PROXY_PORT="${PROD_PROXY_PORT:-16382}"
FLY_API_APP="${FLY_API_APP:-health-tracker-api-dev}"
DUMP_FILE="${DUMP_FILE:-/tmp/health-dev-migrate.dump}"

DRY_RUN=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

docker_pg_dump() {
  docker run --rm -e PGPASSWORD="$DEV_PASS" -v /tmp:/tmp postgres:16 \
    pg_dump -Fc --no-owner --no-privileges \
    -h host.docker.internal -p "$DEV_PROXY_PORT" -U "$DEV_USER" -d "$SOURCE_DB" \
    -f "$DUMP_FILE"
}

docker_pg_restore() {
  docker run --rm -e PGPASSWORD="$PROD_PASS" -v /tmp:/tmp postgres:16 \
    pg_restore --no-owner --no-privileges --clean --if-exists \
    -h host.docker.internal -p "$PROD_PROXY_PORT" -U "$PROD_USER" -d "$TARGET_DB" \
    "$DUMP_FILE"
}

load_creds() {
  local url app="$1"
  url="$(fly ssh console -a "$app" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r')"
  echo "$url" | sed -n 's|postgresql://\([^:]*\):.*|\1|p'
}

load_pass() {
  local url
  url="$(fly ssh console -a "$1" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r')"
  local pass="${url#postgresql://*:}"
  echo "${pass%%@*}"
}

rls_tables_sql() {
  python3 - <<'PY'
from pathlib import Path
import re
text = Path("backend/app/rls.py").read_text()
tables = re.findall(r'"([^"]+)"', text.split("USER_OWNED_TABLES")[1].split(")")[0])
for t in tables:
    print(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
PY
}

grants_sql() {
  cat <<'SQL'
GRANT USAGE ON SCHEMA public TO "healthtracker-app", "healthtracker-ro";
GRANT ALL ON ALL TABLES IN SCHEMA public TO "healthtracker-app";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "healthtracker-ro";
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO "healthtracker-app";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO "healthtracker-ro";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "healthtracker-app";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "healthtracker-ro";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "healthtracker-app";
SQL
}

count_sql="SELECT 'entries', count(*) FROM entries UNION ALL SELECT 'users', count(*) FROM users UNION ALL SELECT 'labs', count(*) FROM labs;"

start_proxy() {
  local cluster="$1" port="$2"
  if lsof -i ":$port" >/dev/null 2>&1; then
    echo "    proxy port $port already in use"
    return 0
  fi
  fly mpg proxy "$cluster" -p "$port" >/dev/null 2>&1 &
  echo $! >"/tmp/fly-mpg-proxy-${port}.pid"
  sleep 2
}

stop_proxy() {
  local port="$1"
  local pid_file="/tmp/fly-mpg-proxy-${port}.pid"
  if [[ -f "$pid_file" ]]; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
  fi
}

run_counts() {
  local port="$1" db="$2" label="$3" user="$4" pass="$5"
  echo "==> $label"
  docker run --rm -e PGPASSWORD="$pass" postgres:16 \
    psql -h host.docker.internal -p "$port" -U "$user" -d "$db" -Atc "$count_sql" || true
}

cd "$(dirname "$0")/.."
DEV_USER="$(load_creds "$FLY_API_APP")"
DEV_PASS="$(load_pass "$FLY_API_APP")"
PROD_USER="$(load_creds health-tracker-api-prod)"
PROD_PASS="$(load_pass health-tracker-api-prod)"

echo "==> Dev cluster: $DEV_CLUSTER ($SOURCE_DB) → prod cluster: $PROD_CLUSTER ($TARGET_DB)"
start_proxy "$DEV_CLUSTER" "$DEV_PROXY_PORT"
start_proxy "$PROD_CLUSTER" "$PROD_PROXY_PORT"

trap 'stop_proxy "$DEV_PROXY_PORT"; stop_proxy "$PROD_PROXY_PORT"' EXIT

run_counts "$DEV_PROXY_PORT" "$SOURCE_DB" "Pre-migration counts (source)" "$DEV_USER" "$DEV_PASS"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "==> DRY RUN — skipping dump/restore"
  exit 0
fi

echo "==> Temporarily NO FORCE RLS on source (htmigrate) for pg_dump"
rls_sql="$(rls_tables_sql)"
docker run --rm -i -e PGPASSWORD="$DEV_PASS" postgres:16 \
  psql -h host.docker.internal -p "$DEV_PROXY_PORT" -U "$DEV_USER" -d "$SOURCE_DB" \
  -v ON_ERROR_STOP=1 <<<"$rls_sql"

echo "==> pg_dump source"
rm -f "$DUMP_FILE"
docker_pg_dump
echo "    dump size: $(stat -f%z "$DUMP_FILE" 2>/dev/null || stat -c%s "$DUMP_FILE") bytes"

echo "==> pg_restore into $TARGET_DB"
docker_pg_restore

echo "==> Post-restore grants on $TARGET_DB"
docker run --rm -i -e PGPASSWORD="$PROD_PASS" postgres:16 \
  psql -h host.docker.internal -p "$PROD_PROXY_PORT" -U "$PROD_USER" -d "$TARGET_DB" \
  -v ON_ERROR_STOP=1 <<<"$(grants_sql)"

run_counts "$PROD_PROXY_PORT" "$TARGET_DB" "Post-migration counts (target)" "$PROD_USER" "$PROD_PASS"

echo "==> Done"
