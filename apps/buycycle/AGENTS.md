# apps/buycycle

Internal-only buycycle resale deal finder (road/gravel **bikes** and **wheelsets**). Runs on the Raspberry Pi as one Coolify app (Dockerfile build from `F0rge/f0rge` `main`).

- `tracker/tracker.py`: one gentle scrape a day. Limits must stay as they are: `FEED_PAUSE` 1.6 s, `PAGE_PAUSE` 2.2 s, `PAGE_CAP` 150/day, and one 2-minute back-off on 403/429, then stop. History goes to an embedded, local **Turso** DB (`pyturso`, `tracker/storage.py`). No cloud or sync.
- `tracker/migrate_sqlite_to_turso.py`: one-time copy from the legacy SQLite DB, with a row-count check.
- `dashboard/`: a single Primer template (`index.tpl.html`) rendered by `render.py` into `index-bikes.html` / `index-wheels.html`; `serve.py` is the static gzip server. **Primer only**: Primer CSS, Primer View Components CSS and the Primer React DataTable CSS, all vendored, plus Octicons. Add no custom CSS. Layout is purely responsive (`d-md-*`), with no manual toggle.
- Ports: 8095 bikes, 8096 wheels. Tailnet/LAN only: **no domain, no Traefik, no cloudflared route.**
- Data: the `/data` volume (`buycycle.turso.db`, `bikes/`, `wheels/`, `tracker.env`). **This repo is public:** never commit DBs, JSON dumps or the feed key (`BUYCYCLE_API_KEY`, which lives only in `/data/tracker.env`).
- Deploy: manifest component `buycycle` (`target: coolify`, `host: pi`). CI sends the Coolify webhook when this project is affected. The tracker runs as a Coolify scheduled task (`/app/run-tracker.sh`, cron `15 4,5 * * *` UTC, with a DST guard that only runs at 06:xx Europe/Luxembourg). Cutover runbook: [deploy/PI_CUTOVER.md](deploy/PI_CUTOVER.md).
- Checks: `npx nx run buycycle:lint`, `buycycle:format-check`, `buycycle:test`.
