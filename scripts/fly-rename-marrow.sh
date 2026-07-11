#!/usr/bin/env bash
# Marrow Fly rename helper — backup, create apps, clone secrets, attach MPG, rename DBs.
#
# Prerequisites: flyctl authenticated, docker (postgres:16), repo at root.
#
# Usage:
#   ./scripts/fly-rename-marrow.sh create-apps
#   ./scripts/fly-rename-marrow.sh clone-secrets
#   ./scripts/fly-rename-marrow.sh attach-mpg [--db fly-db|health_dev]
#   ./scripts/fly-rename-marrow.sh baseline-counts
#   ./scripts/fly-rename-marrow.sh rename-databases
#   ./scripts/fly-rename-marrow.sh copy-databases
#   ./scripts/fly-rename-marrow.sh attach-mpg-renamed
#
set -euo pipefail

CLUSTER="${CLUSTER:-z23750v13yl096d1}"
PROXY_PORT="${PROXY_PORT:-16401}"
BASELINE_FILE="${BASELINE_FILE:-/tmp/marrow-rename/baseline.txt}"

OLD_API_DEV=health-tracker-api-dev
OLD_API_PROD=health-tracker-api-prod
OLD_MCP_DEV=health-tracker-mcp-dev
OLD_MCP_PROD=health-tracker-mcp-prod
OLD_WEB_DEV=health-tracker-web-dev
OLD_WEB_PROD=health-tracker-web-prod

NEW_API_DEV=marrow-dev
NEW_API_PROD=marrow
NEW_MCP_DEV=marrow-mcp-dev
NEW_MCP_PROD=marrow-mcp
NEW_WEB_DEV=marrow-ui-dev
NEW_WEB_PROD=marrow-ui

DB_SKIP='^(DATABASE_URL|MIGRATION_DATABASE_URL|MCP_READONLY_DATABASE_URL)$'

clone_secrets() {
  local src="$1" dst="$2"
  echo "==> clone secrets $src -> $dst"
  local names
  names="$(flyctl secrets list -a "$src" 2>/dev/null | awk 'NR>1 {print $1}' | grep -v '^NAME$' || true)"
  local args=()
  for name in $names; do
    if [[ "$name" =~ $DB_SKIP ]]; then
      continue
    fi
    local val
    val="$(flyctl ssh console -a "$src" -C "printenv $name" 2>/dev/null | tail -1 | tr -d '\r')"
    if [[ -z "$val" ]]; then
      echo "    skip $name (empty)"
      continue
    fi
    args+=("$name=$val")
  done
  if ((${#args[@]} > 0)); then
    flyctl secrets set "${args[@]}" -a "$dst" --stage
  fi
}

patch_cors() {
  local api_app="$1" web_url="$2" api_url="$3"
  local cors
  cors="$(flyctl ssh console -a "$api_app" -C 'printenv CORS_ORIGINS' 2>/dev/null | tail -1 | tr -d '\r' || true)"
  if [[ -z "$cors" ]]; then
    cors="[\"$web_url\",\"$api_url\",\"http://localhost:3000\"]"
  else
  cors="$(python3 - "$cors" "$web_url" "$api_url" <<'PY'
import json, sys
origins = json.loads(sys.argv[1])
for url in (sys.argv[2], sys.argv[3]):
    if url not in origins:
        origins.append(url)
print(json.dumps(origins))
PY
)"
  fi
  flyctl secrets set "CORS_ORIGINS=$cors" -a "$api_app" --stage
}

create_apps() {
  for app in "$NEW_API_PROD" "$NEW_API_DEV" "$NEW_MCP_PROD" "$NEW_MCP_DEV" "$NEW_WEB_PROD" "$NEW_WEB_DEV"; do
    if flyctl apps list 2>/dev/null | awk '{print $1}' | grep -qx "$app"; then
      echo "==> $app already exists"
    else
      echo "==> creating $app"
      flyctl apps create "$app" -y
    fi
  done
}

clone_all_secrets() {
  clone_secrets "$OLD_API_DEV" "$NEW_API_DEV"
  clone_secrets "$OLD_API_PROD" "$NEW_API_PROD"
  clone_secrets "$OLD_MCP_DEV" "$NEW_MCP_DEV"
  clone_secrets "$OLD_MCP_PROD" "$NEW_MCP_PROD"
  patch_cors "$NEW_API_DEV" "https://marrow-ui-dev.fly.dev" "https://marrow-dev.fly.dev"
  patch_cors "$NEW_API_PROD" "https://marrow-ui.fly.dev" "https://marrow.fly.dev"
  flyctl secrets deploy -a "$NEW_API_DEV"
  flyctl secrets deploy -a "$NEW_API_PROD"
  flyctl secrets deploy -a "$NEW_MCP_DEV"
  flyctl secrets deploy -a "$NEW_MCP_PROD"
}

attach_mpg_legacy() {
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_PROD" -d fly-db -u healthtracker-app --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_PROD" -d fly-db -u htmigrate --variable-name MIGRATION_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_PROD" -d fly-db -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_PROD" -d fly-db -u healthtracker-ro --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_DEV" -d health_dev -u healthtracker-app --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_DEV" -d health_dev -u htmigrate --variable-name MIGRATION_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_DEV" -d health_dev -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_DEV" -d health_dev -u healthtracker-ro --variable-name DATABASE_URL
}

attach_mpg_renamed() {
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_PROD" -d marrow -u healthtracker-app --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_PROD" -d marrow -u htmigrate --variable-name MIGRATION_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_PROD" -d marrow -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_PROD" -d marrow -u healthtracker-ro --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_DEV" -d marrow_dev -u healthtracker-app --variable-name DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_API_DEV" -d marrow_dev -u htmigrate --variable-name MIGRATION_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_DEV" -d marrow_dev -u healthtracker-ro --variable-name MCP_READONLY_DATABASE_URL
  flyctl mpg attach "$CLUSTER" -a "$NEW_MCP_DEV" -d marrow_dev -u healthtracker-ro --variable-name DATABASE_URL
}

count_sql="SELECT 'entries', count(*) FROM entries UNION ALL SELECT 'users', count(*) FROM users UNION ALL SELECT 'labs', count(*) FROM labs;"

baseline_counts() {
  mkdir -p "$(dirname "$BASELINE_FILE")"
  flyctl mpg proxy "$CLUSTER" -p "$PROXY_PORT" >/tmp/marrow-rename/proxy.log 2>&1 &
  echo $! >/tmp/marrow-rename/proxy.pid
  sleep 3
  local prod_user prod_pass dev_user dev_pass prod_db dev_db
  prod_user="$(flyctl ssh console -a "$NEW_API_PROD" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r' | sed -n 's|postgresql://\([^:]*\):.*|\1|p')"
  prod_pass="$(flyctl ssh console -a "$NEW_API_PROD" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r' | sed 's|.*://[^:]*:||;s|@.*||')"
  dev_user="$(flyctl ssh console -a "$NEW_API_DEV" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r' | sed -n 's|postgresql://\([^:]*\):.*|\1|p')"
  dev_pass="$(flyctl ssh console -a "$NEW_API_DEV" -C 'printenv MIGRATION_DATABASE_URL' 2>/dev/null | tail -1 | tr -d '\r' | sed 's|.*://[^:]*:||;s|@.*||')"
  prod_db="${PROD_DB:-marrow}"
  dev_db="${DEV_DB:-marrow_dev}"
  {
    echo "=== $prod_db ==="
    docker run --rm -e PGPASSWORD="$prod_pass" postgres:16 \
      psql -h host.docker.internal -p "$PROXY_PORT" -U "$prod_user" -d "$prod_db" -Atc "$count_sql"
    echo "=== $dev_db ==="
    docker run --rm -e PGPASSWORD="$dev_pass" postgres:16 \
      psql -h host.docker.internal -p "$PROXY_PORT" -U "$dev_user" -d "$dev_db" -Atc "$count_sql"
  } | tee "$BASELINE_FILE"
  kill "$(cat /tmp/marrow-rename/proxy.pid)" 2>/dev/null || true
}

scale_old_apps() {
  local count="${1:-0}"
  for app in "$OLD_API_DEV" "$OLD_API_PROD" "$OLD_MCP_DEV" "$OLD_MCP_PROD" "$OLD_WEB_DEV" "$OLD_WEB_PROD"; do
    echo "==> scale $app -> $count"
    flyctl scale count "$count" -a "$app" -y 2>/dev/null || true
  done
}

rename_databases() {
  echo "NOTE: ALTER DATABASE requires postgres owner on Fly MPG." >&2
  echo "Use copy-databases instead (pg_dump/pg_restore to marrow + marrow_dev)." >&2
  exit 1
}

copy_databases() {
  scale_old_apps 0
  for app in "$NEW_API_DEV" "$NEW_API_PROD" "$NEW_MCP_DEV" "$NEW_MCP_PROD" "$NEW_WEB_DEV" "$NEW_WEB_PROD"; do
    flyctl scale count 0 -a "$app" -y 2>/dev/null || true
  done
  echo "==> Create target DBs if missing, then run pg_dump/restore via docs/fly-cutover-runbook.md"
  echo "    Baseline file: $BASELINE_FILE"
}

cmd="${1:-}"
case "$cmd" in
  create-apps) create_apps ;;
  clone-secrets) clone_all_secrets ;;
  attach-mpg-legacy) attach_mpg_legacy ;;
  attach-mpg-renamed) attach_mpg_renamed ;;
  baseline-counts) baseline_counts ;;
  rename-databases) rename_databases ;;
  copy-databases) copy_databases ;;
  *)
    echo "Usage: $0 {create-apps|clone-secrets|attach-mpg-legacy|attach-mpg-renamed|baseline-counts|rename-databases|copy-databases}" >&2
    exit 1
    ;;
esac
