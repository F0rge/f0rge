#!/usr/bin/env bash
# Copy marrow + marrow_dev from source MPG cluster to target (historical: marrow-db-prod).
# Current f0rge org cluster: f0rge-db (nlkxjo5m3240y93v).
#
# Prerequisites: docker (postgres:16), flyctl, source apps reachable via ssh.
#
# Usage:
#   SOURCE_CLUSTER=z23750v13yl096d1 TARGET_CLUSTER=d1zj5omzqwvryqkv ./scripts/fly-mpg-migrate-cluster.sh
#
set -euo pipefail

SOURCE_CLUSTER="${SOURCE_CLUSTER:-z23750v13yl096d1}"
TARGET_CLUSTER="${TARGET_CLUSTER:-d1zj5omzqwvryqkv}"
WORKDIR="${WORKDIR:-/tmp/marrow-cluster-migrate}"
TARGET_URL_FILE="${TARGET_URL_FILE:-$WORKDIR/target-url.txt}"
SOURCE_PROXY_PORT="${SOURCE_PROXY_PORT:-16510}"
TARGET_PROXY_PORT="${TARGET_PROXY_PORT:-16511}"
SOURCE_API_APP="${SOURCE_API_APP:-marrow}"
SOURCE_API_DEV_APP="${SOURCE_API_DEV_APP:-marrow-dev}"

mkdir -p "$WORKDIR"

rls_no_force_sql() {
  python3 - <<'PY'
from pathlib import Path
import re
text = Path("apps/marrow/backend/app/rls.py").read_text()
tables = re.findall(r'"([^"]+)"', text.split("USER_OWNED_TABLES")[1].split(")")[0])
for t in tables:
    print(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
PY
}

rls_force_sql() {
  python3 - <<'PY'
from pathlib import Path
import re
text = Path("apps/marrow/backend/app/rls.py").read_text()
tables = re.findall(r'"([^"]+)"', text.split("USER_OWNED_TABLES")[1].split(")")[0])
for t in tables:
    print(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY;")
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

parse_url() {
  local url="$1"
  url="${url#postgresql+asyncpg://}"
  url="${url#postgresql://}"
  export PGUSER="${url%%:*}"
  export PGPASSWORD="${url#*:}"
  PGPASSWORD="${PGPASSWORD%%@*}"
}

start_proxy() {
  local cluster="$1" port="$2"
  if lsof -i ":$port" >/dev/null 2>&1; then
    return 0
  fi
  flyctl mpg proxy "$cluster" -p "$port" >"$WORKDIR/proxy-$port.log" 2>&1 &
  echo $! >"$WORKDIR/proxy-$port.pid"
  sleep 3
}

stop_proxy() {
  local port="$1"
  local pid_file="$WORKDIR/proxy-$port.pid"
  if [[ -f "$pid_file" ]]; then
    kill "$(cat "$pid_file")" 2>/dev/null || true
    rm -f "$pid_file"
  fi
}

migrate_db() {
  local src_db="$1" dst_db="$2" src_pass="$3" src_user="$4" dst_pass="$5" dst_user="$6"
  echo "==> migrate $src_db -> $dst_db"
  docker run --rm -e PGPASSWORD="$src_pass" -v "$WORKDIR:/tmp" postgres:16 \
    pg_dump -Fc --no-owner --no-privileges \
    -h host.docker.internal -p "$SOURCE_PROXY_PORT" -U "$src_user" -d "$src_db" \
    -f "/tmp/${src_db}.dump"
  set +e
  docker run --rm -e PGPASSWORD="$dst_pass" -v "$WORKDIR:/tmp" postgres:16 \
    pg_restore --no-owner --no-privileges --clean --if-exists \
    -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$dst_user" -d "$dst_db" \
    "/tmp/${src_db}.dump"
  local rc=$?
  set -e
  if [[ "$rc" -ne 0 && "$rc" -ne 1 ]]; then
    return "$rc"
  fi
  docker run --rm -i -e PGPASSWORD="$dst_pass" postgres:16 \
    psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$dst_user" -d "$dst_db" \
    -v ON_ERROR_STOP=1 <<<"$(grants_sql)"
  docker run --rm -i -e PGPASSWORD="$dst_pass" postgres:16 \
    psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$dst_user" -d "$dst_db" \
    -v ON_ERROR_STOP=1 <<<"$(rls_force_sql)"
}

cd "$(dirname "$0")/.."

echo "==> source $SOURCE_CLUSTER -> target $TARGET_CLUSTER"

SRC_PROD_URL="$(flyctl ssh console -a "$SOURCE_API_APP" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r')"
SRC_DEV_URL="$(flyctl ssh console -a "$SOURCE_API_DEV_APP" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r')"
parse_url "$SRC_PROD_URL"
SRC_PROD_USER="$PGUSER" SRC_PROD_PASS="$PGPASSWORD"
parse_url "$SRC_DEV_URL"
SRC_DEV_USER="$PGUSER" SRC_DEV_PASS="$PGPASSWORD"

# htmigrate on target — URL captured from a prior `fly mpg attach` (see runbook)
if [[ -f "$TARGET_URL_FILE" ]]; then
  DST_HTMIGRATE_URL="$(tr -d '\r' <"$TARGET_URL_FILE")"
else
  TARGET_CRED_APP="${TARGET_CRED_APP:-marrow-dev}"
  DST_HTMIGRATE_URL="$(flyctl ssh console -a "$TARGET_CRED_APP" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r')"
fi
if [[ -z "$DST_HTMIGRATE_URL" ]]; then
  echo "Missing target htmigrate URL — run fly mpg attach on $TARGET_CLUSTER and save to $TARGET_URL_FILE" >&2
  exit 1
fi
parse_url "$DST_HTMIGRATE_URL"
DST_USER="$PGUSER" DST_PASS="$PGPASSWORD"

start_proxy "$SOURCE_CLUSTER" "$SOURCE_PROXY_PORT"
start_proxy "$TARGET_CLUSTER" "$TARGET_PROXY_PORT"
trap 'stop_proxy "$SOURCE_PROXY_PORT"; stop_proxy "$TARGET_PROXY_PORT"' EXIT

echo "==> NO FORCE RLS on source marrow"
docker run --rm -i -e PGPASSWORD="$SRC_PROD_PASS" postgres:16 \
  psql -h host.docker.internal -p "$SOURCE_PROXY_PORT" -U "$SRC_PROD_USER" -d marrow \
  -v ON_ERROR_STOP=1 <<<"$(rls_no_force_sql)"

echo "==> NO FORCE RLS on source marrow_dev"
docker run --rm -i -e PGPASSWORD="$SRC_DEV_PASS" postgres:16 \
  psql -h host.docker.internal -p "$SOURCE_PROXY_PORT" -U "$SRC_DEV_USER" -d marrow_dev \
  -v ON_ERROR_STOP=1 <<<"$(rls_no_force_sql)"

migrate_db marrow marrow "$SRC_PROD_PASS" "$SRC_PROD_USER" "$DST_PASS" "$DST_USER"
migrate_db marrow_dev marrow_dev "$SRC_DEV_PASS" "$SRC_DEV_USER" "$DST_PASS" "$DST_USER"

echo "==> FORCE RLS on source marrow"
docker run --rm -i -e PGPASSWORD="$SRC_PROD_PASS" postgres:16 \
  psql -h host.docker.internal -p "$SOURCE_PROXY_PORT" -U "$SRC_PROD_USER" -d marrow \
  -v ON_ERROR_STOP=1 <<<"$(rls_force_sql)"

echo "==> FORCE RLS on source marrow_dev"
docker run --rm -i -e PGPASSWORD="$SRC_DEV_PASS" postgres:16 \
  psql -h host.docker.internal -p "$SOURCE_PROXY_PORT" -U "$SRC_DEV_USER" -d marrow_dev \
  -v ON_ERROR_STOP=1 <<<"$(rls_force_sql)"

echo "==> NO FORCE RLS on target marrow (for row counts)"
docker run --rm -i -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow \
  -v ON_ERROR_STOP=1 <<<"$(rls_no_force_sql)"

echo "==> NO FORCE RLS on target marrow_dev (for row counts)"
docker run --rm -i -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow_dev \
  -v ON_ERROR_STOP=1 <<<"$(rls_no_force_sql)"

COUNT_SQL="SELECT 'entries', count(*) FROM entries UNION ALL SELECT 'users', count(*) FROM users UNION ALL SELECT 'labs', count(*) FROM labs;"
echo "==> target counts marrow"
docker run --rm -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow -Atc "$COUNT_SQL"
echo "==> target counts marrow_dev"
docker run --rm -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow_dev -Atc "$COUNT_SQL"

echo "==> FORCE RLS on target marrow"
docker run --rm -i -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow \
  -v ON_ERROR_STOP=1 <<<"$(rls_force_sql)"

echo "==> FORCE RLS on target marrow_dev"
docker run --rm -i -e PGPASSWORD="$DST_PASS" postgres:16 \
  psql -h host.docker.internal -p "$TARGET_PROXY_PORT" -U "$DST_USER" -d marrow_dev \
  -v ON_ERROR_STOP=1 <<<"$(rls_force_sql)"

echo "==> Done — re-attach all apps to $TARGET_CLUSTER next"
