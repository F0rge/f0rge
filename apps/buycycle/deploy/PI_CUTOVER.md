# Buycycle on the Pi (Ops)

Nx project `buycycle` (`apps/buycycle/Dockerfile`) runs on the Pi as one Coolify application. Internal only: host ports 8095 (bikes) and 8096 (wheels), no domain, Traefik or cloudflared route. Data lives on the `buycycle-data` volume at `/data`.

## Releases

A merge to `main` that affects `buycycle` releases its ARM64 Artifact through [the pipeline](../../../.github/deploy/README.md). The Coolify application is a "Docker image" application named `buycycle`. Leo switches it once with [`switch/buycycle.sh`](../../../.github/deploy/switch/buycycle.sh); until then the App fails closed.

| Setting | Value |
|---|---|
| Image | `ghcr.io/f0rge/buycycle`, tag = the released commit (set by each Release) |
| Ports mapping | `8095:8095,8096:8096` |
| Domains | none |
| Persistent storage | `buycycle-data` mounted at `/data` |
| Env | none required (defaults live in the Dockerfile). `TZ=Europe/Luxembourg` is set in the image |
| Health | the Dockerfile `HEALTHCHECK` (requests 8095 and 8096 inside the container). Coolify's own Healthcheck stays off |

## Scheduled task (Coolify → app → Scheduled Tasks)

- Name `buycycle-tracker`, command `/app/run-tracker.sh`, frequency **`15 4,5 * * *`** (Coolify cron runs in UTC). That is 04:15 and 05:15 UTC; the script carries on only when the Europe/Luxembourg hour is 06 and exits 0 otherwise, so there is exactly one run at 06:15 local time all year (CEST → 04:15 UTC, CET → 05:15 UTC). For a manual run at any hour use `BUYCYCLE_FORCE=1 /app/run-tracker.sh`; any arguments, e.g. `--no-scrape --no-fetch`, also bypass the guard.
- Do Releases and the switch outside 06:00–08:00 local time, when the scrape writes to the volume.

## Back to the systemd stack

Before Coolify, the tracker and both dashboards ran as systemd units on the Pi. Their database, `~/buycycle-tracker/buycycle.db`, is never modified by the Coolify app. To go back:

```sh
# Coolify: stop the buycycle app (frees 8095/8096), then on the Pi:
sudo systemctl enable --now bikes-dashboard.service wheels-dashboard.service buycycle-tracker.timer
```

Days scraped since the Coolify app took over exist only in the volume's `buycycle.turso.db`.
