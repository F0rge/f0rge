#!/bin/sh
# Daily scrape (Coolify scheduled task). Coolify cron runs in UTC, so it is scheduled at "15 4,5 * * *" and this
# script only proceeds when it is 06:xx in Europe/Luxembourg: exactly one run a day across CET/CEST.
# Set BUYCYCLE_FORCE=1 (or pass args, e.g. --no-scrape --no-fetch) to run regardless of the hour.
# Reads BUYCYCLE_API_KEY from the volume, never from the repo.
set -eu
if [ "${BUYCYCLE_FORCE:-0}" != "1" ] && [ "$#" -eq 0 ]; then
  h=$(TZ=Europe/Luxembourg date +%H)
  if [ "$h" != "06" ]; then
    echo "buycycle tracker: Luxembourg hour is $h, not 06; skipping (DST guard)"
    exit 0
  fi
fi
[ -f /data/tracker.env ] && { set -a; . /data/tracker.env; set +a; }
exec /app/.venv/bin/python /app/tracker/tracker.py "$@"
