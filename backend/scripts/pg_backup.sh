#!/bin/sh
set -euo pipefail

# Weekly Postgres backup for health-tracker.
# Writes a custom-format dump to /backups and rotates to the 4 most recent.
# Expects PGHOST/PGUSER/PGPASSWORD/PGDATABASE in the environment.

dump_file="/backups/health-$(date +%Y%m%d).dump"

pg_dump -Fc -f "$dump_file"

# Keep the 4 most recent dumps; remove the rest.
ls -t /backups/health-*.dump | tail -n +5 | xargs -r rm -v
