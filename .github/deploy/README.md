# Deploy manifest

Single source of truth for **which Nx projects deploy where**. The orchestrator
(`.github/workflows/deploy-reusable.yml`) reads this file, intersects with `nx
affected`, and delegates to Fly or Coolify executors.

## Add app #3

1. Land code under `apps/<name>/` with `project.json` tags `platform:py` or
   `platform:ts` (and optional `deploy-target:*`).
2. Add a `components.<id>` block below.
3. For **Fly**: set `target: fly`, `fly.role` (`api` | `frontend`), and per-env
   config paths.
4. For **Coolify (Pi)**: set `target: coolify`, `coolify.app_uuid`, and
   `webhook_secret_env` (name of a GitHub Actions secret holding the app's
   `manual_webhook_secret_github` value).
5. Set `branches` — e.g. `[main]` for prod-only Pi apps, `[develop, main]` for
   Fly dev+prod.
6. Add repo secrets if new Coolify webhooks are needed:
   - `COOLIFY_BASE_URL` (e.g. `https://coolify.taxpilot.lu`)
   - `COOLIFY_WEBHOOK_<APP>_*` per component

## Secrets

| Secret | Used by |
|--------|---------|
| `FLY_API_TOKEN` | Marrow Fly deploy |
| `COOLIFY_BASE_URL` | Coolify webhook POST base |
| `COOLIFY_WEBHOOK_DK_BACKEND` | dk-tag-printer-backend |
| `COOLIFY_WEBHOOK_DK_FRONTEND` | dk-tag-printer-frontend |

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

After the first successful `main` deploy from f0rge, archive the standalone repo:
`gh repo archive leothesouthafrican/dk_tag_printer`.

See also [manifest.yml](manifest.yml) and [plan_deploy.py](plan_deploy.py).
