#!/bin/sh
# Daily scrape (Coolify scheduled task, 06:15 Europe/Luxembourg). Reads BUYCYCLE_API_KEY from the volume, never from the repo.
set -eu
[ -f /data/tracker.env ] && { set -a; . /data/tracker.env; set +a; }
exec /app/.venv/bin/python /app/tracker/tracker.py "$@"
