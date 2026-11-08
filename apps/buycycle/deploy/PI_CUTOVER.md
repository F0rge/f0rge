# Buycycle → Coolify on the Pi: cutover runbook (Ops)

Pi: aarch64, Coolify v4.0.0-beta.473 (Scheduled Tasks available). Internal only. Coolify settings of other apps stay untouched. No domain, Traefik or cloudflared route for this app.

## 1. Create the Coolify app (needs Leonardo's OK)
| Field | Value |
|---|---|
| Source | **Public GitHub** (source_id=0, no key; same as the dk apps): `https://github.com/F0rge/f0rge` |
| Branch | `main` |
| Build pack | Dockerfile |
| Base directory | `/` |
| Dockerfile | `/apps/buycycle/Dockerfile` |
| Watch paths | `apps/buycycle/**` |
| Ports mapping | `8095:8095,8096:8096` (bind to the tailnet IP `100.103.61.77:` or the LAN IP if you want to keep it off 0.0.0.0) |
| Domains | none (leave empty, so no Traefik route) |
| Persistent storage | volume `buycycle-data` mounted at `/data` |
| Env | none required (defaults live in the Dockerfile). `TZ=Europe/Luxembourg` is already set |
| Auto deploy | **on** (`is_auto_deploy_enabled: true`). Coolify v4 blocks the manual webhook CI uses when this is off. This repo has no push webhooks, so on does not double-deploy. |
| Health check | Dockerfile HEALTHCHECK (curls 8095/8096 inside the container) |

Then:
- App UUID `xi0qwpbyl2d8gf8u3xl13jkv` is set in `.github/deploy/manifest.yml`.
- Copy the app's manual GitHub webhook secret into the GitHub Actions secret `COOLIFY_WEBHOOK_BUYCYCLE`. Until that's set, the deploy job skips cleanly.
- CI sends the changed paths in that webhook (`commits[].added`, `modified`, `removed`, from `git diff --name-status`) so this watch path matches and Coolify queues the deploy.

## 2. Scheduled task (Coolify → app → Scheduled Tasks)
- Name `buycycle-tracker`, command `/app/run-tracker.sh`, frequency **`15 4,5 * * *`** (Coolify cron runs in UTC). That's 04:15 and 05:15 UTC; the script carries on only when the Europe/Luxembourg hour is 06 and exits 0 otherwise, so there's exactly one run at 06:15 local time all year (CEST → 04:15 UTC, CET → 05:15 UTC). For a manual run at any hour use `BUYCYCLE_FORCE=1 /app/run-tracker.sh`; any arguments, e.g. `--no-scrape --no-fetch`, also bypass the guard.
- The scrape timing and limits are unchanged from the old `buycycle-tracker.timer`.

## 3. Cutover (do it outside 06:00–08:00 so you don't collide with a scrape)
```sh
# on the Pi
sudo systemctl disable --now buycycle-tracker.timer bikes-dashboard.service wheels-dashboard.service   # frees 8095/8096
TS=$(date +%Y%m%d-%H%M); B=/home/leo/buycycle-backup-$TS; mkdir -p $B
cp -a /home/leo/buycycle-tracker /home/leo/bikes-dashboard /home/leo/wheels-dashboard $B/
sudo cp /etc/systemd/system/buycycle-tracker.* /etc/systemd/system/*-dashboard.service $B/ 2>/dev/null
grep '^K = ' $B/buycycle-tracker/tracker.py     # old feed key value
```
Deploy the app once from Coolify (or merge to `main`), then seed the volume:
```sh
C=$(docker ps --filter name=<app-uuid> -q | head -1)
docker cp /home/leo/buycycle-tracker/buycycle.db $C:/data/buycycle.db
docker exec $C sh -c 'printf "BUYCYCLE_API_KEY=%s\n" "<value>" > /data/tracker.env && chmod 600 /data/tracker.env'
docker exec $C /app/.venv/bin/python /app/tracker/migrate_sqlite_to_turso.py --src /data/buycycle.db --dst /data/buycycle.turso.db   # must print OK per table
for k in bikes wheels; do docker cp /home/leo/$k-dashboard/. $C:/data/$k/; done    # current data.json etc. so the UI isn't empty until 06:15
docker exec $C /app/run-tracker.sh --no-scrape --no-fetch                           # rebuild JSON from Turso, no network
curl -sI http://100.103.61.77:8095/ | head -1; curl -sI http://100.103.61.77:8096/ | head -1
```
(`docker cp` writes as root; if needed, run `docker exec -u 0 $C chown -R 1000:1000 /data`.)

## 4. Rollback
```sh
# Coolify: stop the buycycle app (frees 8095/8096)
sudo systemctl enable --now bikes-dashboard.service wheels-dashboard.service buycycle-tracker.timer
```
The legacy `/home/leo/buycycle-tracker/buycycle.db` is never modified by the new app, so the old stack carries on from where it stopped. Days scraped after cutover exist only in the volume's `buycycle.turso.db`.
