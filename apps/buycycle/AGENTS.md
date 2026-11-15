> Canonical decisions: [`docs/adr/README.md`](../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# apps/buycycle

Private buycycle resale deal finder (road/gravel **bikes** and **wheelsets**).
The running legacy service and the unreleased ADR migration are separate below.

## ADR migration source

- `backend/`: Rust/Actix/Diesel with PostgreSQL, shared verified Cloudflare Access
  identity and API errors; Rust owns calculations and the durable collector.
- `frontend/`: standalone React/Vite/strict TypeScript, actual shared Primer and
  TanStack Query/Router/Form, generated OpenAPI client. `libs/primer/` owns shared
  bricks, form adapters and Storybook; do not copy them into the app.
- `migration/`: lossless legacy export/import and PostgreSQL restore rehearsals.
  Preserve all five legacy tables, browser archives, history, nulls and units.
- `ops/`: one-command local startup, tested ARM64 image, private-origin Compose,
  controlled migration, backup/monitor sources and protected release preparation.
  Read [the operations runbook](ops/README.md) before local, image or provider work.
- Read [the work plan](docs/adr-migration-plan.md) and
  [readiness evidence](docs/ops-readiness.md) before claiming completion. Leo chose
  Buycycle first and the holiday-explorer pilot later (P-010), and Cloudflare
  Access email-code login for this personal app (P-035). The new API verifies the
  assertion itself; it never trusts a caller-supplied email header.
- Keep collection disabled in local/CI. Use synthetic identity and actual
  disposable PostgreSQL. No live scraping, emails or production writes in tests.
- The new origin publishes no app ports. The intended authenticated domain is a
  future cutover configuration; the running legacy ports remain untouched.
- Do not start the old collector beside the new one, reset its safety ledger,
  replace production data, or resume stale Turso after any PostgreSQL writes.
  Preserve every original browser origin/profile export before cutover.
- PR checks: `buycycle-backend:{format-check,lint,test,build}`,
  `buycycle-frontend:{lint,typecheck,test,build,codegen:check,e2e}`,
  `f0rge-primer:{lint,typecheck,test,storybook-build}` and
  `buycycle-ops:{lint,format-check,test}` through Nx. Backend integration tests
  require the explicit synthetic `BUYCYCLE_TEST_DATABASE_URL`; missing PostgreSQL
  fails rather than skipping. The ARM64 `container-test` is uncached.
- Release preparation is not activation: successful checks, receipts or a merge
  do not supply Leo's release approval. Provider identity, grants, secret custody,
  writer fencing, current encrypted recovery and exact artifact verification must
  pass the release gates before an authorized cutover.

## Retained legacy runtime and recovery inventory

The existing Pi service is one Coolify app built from source. These files remain
for characterization and data-preserving recovery until a separately approved
cutover; they are not the new backend/frontend or an approved ADR exception.

- Market columns (same comps as Avg ask: brand + model key, wheels also brake and rim, bikes also year ±1; the listing itself left out). Z-score is (ask − mean) / stdev of the live comps, blank under 2 comps or a zero stdev, and marked low under 5. €/day is the higher of buycycle's original price and the highest `price_history` snapshot, minus the current price, divided by days listed; 0 if the ask did not fall; blank with no history. A snapshot drop still counts when the original price does not show it. Sold % is how many of those comps, first seen at least 30 days ago, disappeared within 30 days. Disappeared means `gone_at` was set on a complete daily pass that no longer listed them (sold or withdrawn — buycycle has no sold status). The denominator is shown; blank under 5. vs sell is days listed ÷ the median days-to-disappear of comps that have disappeared; blank under 5. History only goes back to when the tracker started, so Sold % and vs sell are mostly blank until that window is long enough. Do not invent a value. Next up is the lowest live comp ask strictly above this one, with the gap in euros and percent and days since that comp's first_seen; ties show the longest-listed and +N; ≥ when that first_seen is the earliest date in the published file. priciest when comps exist but none is higher; a dash when there are none. The page computes it from data.json, so a redeploy shows it before the next tracker run.
- `tracker/tracker.py`: one gentle scrape a day. Limits must stay as they are: `FEED_PAUSE` 1.6 s, `PAGE_PAUSE` 2.2 s, `PAGE_CAP` 150/day, and one 2-minute back-off on 403/429, then stop. History goes to an embedded, local **Turso** DB (`pyturso`, `tracker/storage.py`). No cloud or sync.
- Tracker safety: `tracker/safety.py` locks the canonical DB path before opening Turso and keeps a durable daily budget/block ledger beside it (`<db>-tracker.lock`, `<db>-tracker-safety.json`). Preserve these operational files with the data volume. CLI/force flags do not bypass the lock, daily quota or blocked state. Missing state with existing data holds collection for the activation day; invalid state fails closed. Do not delete/reset the ledger to resume requests. Restore the DB and ledger together; if the current day's consumed quota cannot be proved, keep collection paused until the next Luxembourg day. The five legacy database tables and browser data formats remain unchanged.
- `tracker/migrate_sqlite_to_turso.py`: one-time copy from the legacy SQLite DB, with a row-count check.
- `dashboard/`: a single Primer template (`index.tpl.html`) rendered by `render.py` into `index-bikes.html` / `index-wheels.html`; `serve.py` is the static gzip server. **Primer only**: Primer CSS, Primer View Components CSS and the Primer React DataTable CSS, all vendored, plus Octicons. Add no custom CSS. Layout is purely responsive (`d-md-*`), with no manual toggle.
- Ports: 8095 bikes, 8096 wheels. Tailnet/LAN only: **no domain, no Traefik, no cloudflared route.**
- Data: the `/data` volume (`buycycle.turso.db`, `bikes/`, `wheels/`, `tracker.env`). **This repo is public:** never commit DBs, JSON dumps or the feed key (`BUYCYCLE_API_KEY`, which lives only in `/data/tracker.env`).
- Release hold: manifest component `buycycle` (`target: coolify`, `host: pi`) is historical target inventory. The existing **Deploy** workflow is disabled; the proposed preparation/hold workflows send no Coolify webhook. The configured GitHub `production` environment does not protect direct Coolify operations, and runtime provider state has not been checked for this change. Before authorized release work, read [the remaining artifact, secret migration and independent approval requirements](../../.github/deploy/README.md); Leo must explicitly approve every production release.
- Documented runtime: the tracker runs as a Coolify scheduled task (`/app/run-tracker.sh`, cron `15 4,5 * * *` UTC, with a DST guard that only runs at 06:xx Europe/Luxembourg). Verify current provider state before using the historical cutover runbook: [deploy/PI_CUTOVER.md](deploy/PI_CUTOVER.md).
- Checks: `npx nx run buycycle:lint`, `buycycle:format-check`, `buycycle:test`.

The original [brief](docs/migration-brief.md) and [clickable mockup](docs/migration-mockup.html)
explain the agreed journeys. The mockup uses synthetic scenarios. Current
implementation and release gaps live in the work plan and readiness evidence.
