# Deploy manifest

Single source of truth for **which Nx projects deploy where**. The orchestrator
(`.github/workflows/deploy-reusable.yml`) reads this file, intersects with `nx
affected`, and delegates to Railway smoke or Coolify executors.

Marrow ships via **Railway GitHub autodeploy**; Actions only plans + smokes.
dk tag-printer and buycycle run on Coolify (Pi). Firstout is a **separate Railway
project** (not Marrow `zoological-fulfillment`),
**`main` only**. Hosts: `firstout.co.za` /
`api.firstout.co.za` (Swagger at `/docs`).

## Add app #3

1. Land code under `apps/<name>/` with `project.json` tags `platform:py` or
   `platform:ts` (and optional `deploy-target:*`).
2. Add a `components.<id>` block below.
3. For **Railway (marrow)**: set `target: railway`, `railway.role`
   (`api` | `frontend`), and per-env `railway.health_url` (smoke target).
   MCP URLs go under `also_deploys`.
4. For **Coolify (Pi)**: set `target: coolify`, `coolify.app_uuid`, and
   `webhook_secret_env` (name of a GitHub Actions secret holding the app's
   `manual_webhook_secret_github` value).
5. Set `branches` — e.g. `[main]`. `main` is the only deployed branch;
   there is no develop environment.
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
| `SMOKE_EMAIL` / `SMOKE_PASSWORD` | Optional Railway auth smoke |

`FLY_API_TOKEN` is unused after the Railway cutover (safe to delete from GitHub
secrets after the 48h Fly rollback window).

## Coolify monorepo settings (per app)

| Field | dk tag printer |
|-------|----------------|
| Repo | `F0rge/f0rge` |
| Branch | `main` |
| Base directory | `/` |
| Dockerfile | `apps/dk/tag-printer/backend/Dockerfile` or `.../frontend/Dockerfile` |
| Watch paths | `apps/dk/tag-printer/backend/**` or `.../frontend/**` |
| Frontend build-time env | `NEXT_PUBLIC_API_URL=https://tags-api.leo-figueiredo.com` |
| Backend runtime env | `CORS_ORIGINS=https://tags.leo-figueiredo.com` |

The manual webhook body is one commit (`id`, `added`, `modified`, `removed`)
from `git diff --name-status` between the deployed SHA and the Coolify base
(`NX_PARENT` when `NX_BASE == NX_HEAD`, otherwise `NX_BASE`). Coolify matches
those paths to each app's watch paths. Each component is signed with its own
secret (`webhook_secret_env`). That value must equal the app's manual GitHub
webhook secret in Coolify. Sibling apps on the same repo and branch answer
`Invalid signature` because the endpoint checks each app's own secret; the job
only requires this app's entry to say `Deployment queued.`

Disable Coolify GitHub App auto-deploy on dk apps once Actions webhooks are
verified — deploy is CI-gated via `deploy-reusable.yml` on `main` push.

Internal-only Coolify components (e.g. `buycycle`, `host: pi`) omit `health_url`:
runners can't reach the Pi, so the job relies on Coolify's `queued` response and
skips the health smoke. A `TODO…` placeholder `app_uuid` also skips. Buycycle
cutover: [apps/buycycle/deploy/PI_CUTOVER.md](../../apps/buycycle/deploy/PI_CUTOVER.md).

Coolify steps **skip (success)** when webhook secrets are missing or Coolify
returns `Deployments disabled` for the app — so a parked Pi app does not fail
the marrow Railway smoke.

See also [manifest.yml](manifest.yml) and [plan_deploy.py](plan_deploy.py).

## Known: Deploy runs from the default branch's workflow file
`deploy.yml` is triggered by `workflow_run`, which always uses the workflow file
(and the local `./.github/workflows/deploy-reusable.yml` it calls) from the
repository **default branch**. Until the default branch is switched from
`develop` to `main` (Settings → General → Default branch), changes to these two
files on `main` do not take effect for automatic deploys. The checked-out code,
manifest and `plan_deploy.py` do come from the deployed `main` SHA.
