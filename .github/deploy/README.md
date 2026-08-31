# Deploy manifest

Single source of truth for **which Nx projects deploy where**. The orchestrator
(`.github/workflows/deploy-reusable.yml`) reads this file, intersects with `nx
affected`, and delegates to Railway smoke or Coolify executors.

Marrow ships via **Railway GitHub autodeploy**; Actions only plans + smokes.
dk tag-printer remains on Coolify (Pi). Vellano is Railway **develop only**
(services provisioned separately; CoS patches `health_url` after they exist).

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
5. Set `branches` — e.g. `[main]` for prod-only Pi apps, `[develop, main]` for
   marrow.
6. Add repo secrets if new Coolify webhooks are needed:
   - `COOLIFY_BASE_URL` (e.g. `https://coolify.taxpilot.lu`)
   - `COOLIFY_WEBHOOK_<APP>_*` per component

## Secrets

| Secret | Used by |
|--------|---------|
| `COOLIFY_BASE_URL` | Coolify webhook POST base |
| `COOLIFY_WEBHOOK_DK_BACKEND` | dk-tag-printer-backend |
| `COOLIFY_WEBHOOK_DK_FRONTEND` | dk-tag-printer-frontend |
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

Disable Coolify GitHub App auto-deploy on dk apps once Actions webhooks are
verified — deploy is CI-gated via `deploy-reusable.yml` on `main` push.

Coolify steps **skip (success)** when webhook secrets are missing or Coolify
returns `Deployments disabled` for the app — so a parked Pi app does not fail
the marrow Railway smoke.

See also [manifest.yml](manifest.yml) and [plan_deploy.py](plan_deploy.py).
