#!/usr/bin/env bash
# Dry-run migration: Pi Postgres + local photo volumes → Fly MPG + Tigris.
#
# Does NOT touch production Pi services. Requires:
#   - pg_dump access to Pi Postgres (SSH tunnel or VPN)
#   - flyctl + FLY_API_TOKEN
#   - Target MPG cluster ID (shared: z23750v13yl096d1)
#   - Target database: marrow (prod) or marrow_dev (dev Fly stack)
#
# Usage:
#   PI_DATABASE_URL=postgresql://health:***@pi-host:5432/health \
#   FLY_MPG_CLUSTER=z23750v13yl096d1 \
#   TARGET_DB=marrow_dev \
#   ./scripts/fly-migrate-from-pi.sh --dry-run
#
set -euo pipefail

DRY_RUN=1
PI_DATABASE_URL="${PI_DATABASE_URL:-}"
FLY_MPG_CLUSTER="${FLY_MPG_CLUSTER:-z23750v13yl096d1}"
TARGET_DB="${TARGET_DB:-marrow_dev}"
SCRATCH_DB="${SCRATCH_DB:-health_tracker_scratch}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) DRY_RUN=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PI_DATABASE_URL" ]]; then
  echo "PI_DATABASE_URL is required" >&2
  exit 1
fi

DUMP_FILE="$(mktemp -t health-pi-XXXXXX.dump)"
cleanup() { rm -f "$DUMP_FILE"; }
trap cleanup EXIT

echo "==> pg_dump from Pi source (custom format)"
pg_dump -Fc --no-owner --no-privileges "$PI_DATABASE_URL" -f "$DUMP_FILE"
DUMP_BYTES=$(stat -f%z "$DUMP_FILE" 2>/dev/null || stat -c%s "$DUMP_FILE")
echo "    dump size: ${DUMP_BYTES} bytes"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "==> DRY RUN — skipping restore to Fly MPG"
  echo "    Would restore to cluster: $FLY_MPG_CLUSTER (database: $SCRATCH_DB)"
  echo "    Next: fly mpg import / pg_restore via fly mpg proxy"
  echo "    Then: copy Pi photo + lab_attachment volumes to Tigris under Leo user prefix"
  exit 0
fi

echo "==> Restore to Fly MPG (requires fly mpg proxy + pg_restore)"
echo "    Manual step — see docs/fly-cutover-runbook.md"
exit 0
