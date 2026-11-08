# Deploy manifest

Single source of truth for **which Nx projects deploy where**. The orchestrator
(`.github/workflows/deploy-reusable.yml`) reads this file, intersects with `nx
affected`, and delegates to Railway smoke or Coolify executors.

Committed configuration describes **Railway deployment plus Actions smoke** for Marrow. Check current provider triggers before an authorized release; this file does not enable them or grant production approval.
dk tag-printer, buycycle, and environment-monitor run on Coolify (Pi). Firstout is a **separate Railway
project** (not Marrow),
**`main` only**, in Railway environment `production`
(`9f7b0c34-bd95-442b-b746-a9791dcc2895`). Hosts: `firstout.co.za` /
`api.firstout.co.za` (Swagger at `/docs`).

DasKasas storefront is a separate Railway project (`d58a2884-d366-4230-9555-8b7bb4e42d4f`),
production environment `d73ff2d5-816d-4bc8-85b4-71a85b0398fa`, with services
`storefront` and `storefront-commerce`. Its `apps/storefront/` Railway configs are
outside this manifest; verify both services separately for an approved release.

## Add an app

1. Land code under `apps/<name>/` with `project.json` tags `platform:py` or
   `platform:ts` (and optional `deploy-target:*`).
2. Add a `components.<id>` block below.
3. For **Railway smoke**: set `target: railway`, `railway.role`
   (`api` | `frontend`), and per-env `railway.health_url` (smoke target).
   MCP URLs go under `also_deploys`.
4. For **Coolify (Pi)**: set `target: coolify`, `coolify.app_uuid`, and
   `webhook_secret_env` (name of a GitHub Actions secret holding the app's
   `manual_webhook_secret_github` value).
5. Set `branches: [main]`. PRs target `main`; existing remote refs and historical
   environment names are separate inventory.
6. Add repo secrets if new Coolify webhooks are needed:
   - `COOLIFY_BASE_URL` (e.g. `https://coolify.taxpilot.lu`)
   - `COOLIFY_WEBHOOK_<APP>_*` per component

## Secrets

| Secret | Used by |
|--------|---------|
| `COOLIFY_BASE_URL` | Coolify webhook POST base |
| `COOLIFY_WEBHOOK_DASKASAS_BACKEND` | dk-tag-printer-backend (Coolify app daskasas-backend) |
| `COOLIFY_WEBHOOK_DASKASAS_FRONTEND` | dk-tag-printer-frontend (Coolify app daskasas-frontend) |
| `COOLIFY_WEBHOOK_BUYCYCLE` | buycycle (Pi, internal only; skips while unset) |
| `COOLIFY_WEBHOOK_ENVMON_BACKEND` | environment-monitor-backend (Pi; skips while unset) |
| `COOLIFY_WEBHOOK_ENVMON_FRONTEND` | environment-monitor-frontend (Pi; skips while unset) |
| `SMOKE_EMAIL` / `SMOKE_PASSWORD` | Optional Railway auth smoke |

## Coolify monorepo settings (per app)

| Field | dk tag printer | environment-monitor |
|-------|----------------|---------------------|
| Repo | `F0rge/f0rge` | `F0rge/f0rge` |
| Branch | `main` | `main` |
| Base directory | `/` | `apps/environment-monitor/backend` or `.../frontend` |
| Dockerfile | `apps/dk/tag-printer/backend/Dockerfile` or `.../frontend/Dockerfile` | `Dockerfile` (relative to that base) |
| Watch paths | `apps/dk/tag-printer/backend/**` or `.../frontend/**` | `apps/environment-monitor/backend/**` or `.../frontend/**` |
| Frontend build-time env | `NEXT_PUBLIC_API_URL=https://tags-api.leo-figueiredo.com` | keep existing `BACKEND_URL` |
| Backend runtime env | `CORS_ORIGINS=https://tags.leo-figueiredo.com` | keep existing `PYTHONUNBUFFERED` (both apps) |

The manual webhook body is one commit (`id`, `added`, `modified`, `removed`)
from `git diff --name-status` between the deployed SHA and the Coolify base
(`NX_PARENT` when `NX_BASE == NX_HEAD`, otherwise `NX_BASE`). Coolify matches
those paths to each app's watch paths. Each component is signed with its own
secret (`webhook_secret_env`). That value must equal the app's manual GitHub
webhook secret in Coolify. Sibling apps on the same repo and branch answer
`Invalid signature` because the endpoint checks each app's own secret. The job
ignores that answer on apps it did not select. The selected app must queue a
deployment, or return the exact watch-path ignore. `Invalid signature` on the
selected app fails the job.

An explicitly approved release through this legacy webhook path requires the
selected app to accept manual webhooks. Coolify v4 reports `Deployments disabled.`
when `is_auto_deploy_enabled=false`; the job treats that response as failure.
Preserve existing release holds. Changing provider trigger settings needs an
authorized operations task; do not enable them merely to make this workflow pass.

Internal-only Coolify components (e.g. `buycycle`, `environment-monitor-*`, `host: pi`) omit `health_url`:
runners can't reach the Pi, so the job relies on Coolify's `queued` response and
skips the health smoke. A `TODO…` placeholder `app_uuid` also skips. Buycycle
cutover: [apps/buycycle/deploy/PI_CUTOVER.md](../../apps/buycycle/deploy/PI_CUTOVER.md).

Coolify steps **skip (success)** when webhook secrets are missing, the
`app_uuid` is still a `TODO…` placeholder, or Coolify answers HTTP 2xx with
this app's message exactly equal to `Changed files do not match watch paths. Ignoring deployment.`
The watch-path case logs `SKIPPED <app>: Coolify ignored (watch paths)` and
writes that line to the job summary.

HTTP 2xx with this selected app's message exactly equal to `Deployments disabled.`
**fails** the job. `classify_coolify_response` returns `failed` for that
sentence (not `skipped`). The error names the app and its Coolify uuid and
reports that the app does not accept this deployment path. A sibling's copy of that
sentence does not count. Any other 2xx that does not queue a deployment, and
any non-2xx, fails the job. Missing secrets and placeholder uuids still skip,
so an unconfigured Pi app does not fail the marrow Railway smoke.

See also [manifest.yml](manifest.yml) and [plan_deploy.py](plan_deploy.py).

## Known: Deploy runs from the default branch's workflow file
`deploy.yml` is triggered by `workflow_run`, which always uses the workflow file
(and the local `./.github/workflows/deploy-reusable.yml` it calls) from the
repository **default branch** (`main`). A change to these files on `main`
applies to the next automatic Deploy. The checked-out code, manifest, and
`plan_deploy.py` come from the deployed SHA.
