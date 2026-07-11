#!/bin/sh
# Daily Postgres backup for health-tracker.
# Writes a custom-format dump (-Fc, internally compressed) to /backups
# and prunes by count + age. Expects PGHOST/PGUSER/PGPASSWORD/PGDATABASE
# in the environment.

set -eu
# busybox sh supports pipefail
set -o pipefail 2>/dev/null || true

backup_dir="/backups"
keep_days=14
keep_count=14
ts="$(date -u +%Y%m%dT%H%M%SZ)"
dump_file="${backup_dir}/health-${ts}.dump"
log() { printf "[%s] %s\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

mkdir -p "$backup_dir"

log "starting pg_dump (host=$PGHOST db=$PGDATABASE -> $dump_file)"
if ! pg_dump -Fc --no-owner --no-privileges -f "$dump_file"; then
    log "pg_dump FAILED (exit $?), removing partial file"
    rm -f "$dump_file"
    exit 1
fi

size=$(stat -c %s "$dump_file" 2>/dev/null || echo "?")
log "pg_dump OK, size=${size} bytes"

# Retention: keep the $keep_count most recent + drop anything older than $keep_days days.
log "pruning: keep newest $keep_count, drop older than ${keep_days}d"
ls -1t "$backup_dir"/health-*.dump 2>/dev/null | tail -n +$((keep_count + 1)) | xargs -r rm -v
find "$backup_dir" -maxdepth 1 -name "health-*.dump" -mtime "+${keep_days}" -print -delete

log "done"
