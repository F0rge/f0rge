> Canonical decisions: [`docs/adr/README.md`](../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# DevOps Review Playbook

## What this is

Review checklist for infrastructure diffs. Load this when reviewing a PR that touches infrastructure, CI, Docker, Fly deploy, or migrations. Scan the diff, apply the rules below, return JSON findings.

## Scope — files YOU review

- `.github/workflows/**`
- `**/fly*.toml`
- `apps/marrow/backend/Dockerfile`, `apps/marrow/backend/docker-entrypoint.sh`
- `apps/marrow/backend/migrations/versions/*.py` (migration safety + deploy compatibility ONLY)
- `apps/marrow/backend/migrations/env.py`, `apps/marrow/backend/alembic.ini`
- `apps/marrow/frontend/Dockerfile`, `apps/marrow/frontend/next.config.*`
- Root scripts affecting deploy (no `start.sh` in repo)
- `.dockerignore`, `.gitignore`
- Anything affecting Fly apps, MPG, Cloudflare DNS (`marrow-health.com`), CI workflows
- NOT app code under `apps/marrow/backend/app/**` or `apps/marrow/frontend/app/**`

## Hard rules — instant block findings

- **Root build context** — Docker builds must use repo root as context (`docker build -f apps/marrow/backend/Dockerfile .`). Block on `working-directory` in fly deploy that hides `libs/`.
- **Whitelist `.dockerignore`** — must use `*` + `!apps/...` + `!libs/**` pattern. Block on blacklist-only dockerignore that ships the whole repo.
- **No root `uv.lock`** — block on any PR creating `<root>/uv.lock`. Per-project locks only.

- **Migrations are not a startup free-for-all.** Legacy Fly toml files still contain `release_command`. Current Marrow `railway.toml` files contain `preDeployCommand`. Do not add a new Fly deploy. Do not treat either command as Leo's approval to run a production migration. Runtime database credentials stay least-privilege. Destructive migrations still need an explicit recovery note.

- **MPG role DDL on Fly.** Set `FLY_MPG_SKIP_ROLE_DDL=1` on Fly apps; roles are provisioned via `fly mpg users create`, not migration-side DDL on Fly.

- **Secrets in repo.** Block any hardcoded `FLY_API_TOKEN`, database passwords, or JWT secrets.

- **Custom domain without cert plan.** New `marrow-health.com` hostnames need `fly certs add` + Cloudflare DNS-only (grey cloud) + ACME CNAME until issued.

## Fly deploy conventions (historical inventory, not a live check and not a release approval)

| Env | Branch | Apps | Workflow |
|---|---|---|---|
| Prod | `main` | `marrow`, `marrow-mcp`, `marrow-ui` | `ci.yml` (deploy job) |

Deploy order: API (alembic via `release_command`) → MCP (serial); frontend parallel. Jobs: `plan`, `deploy api`, `deploy mcp`, `deploy frontend`, `smoke`. `workflow_dispatch` supports `component=all|api|mcp|frontend`.

MPG cluster: `nlkxjo5m3240y93v` (`f0rge-db`, org `f0rge`). Databases: `marrow` (prod), `marrow_dev` (dev).

Full reference: [README.md](../../README.md#cicd), `.cursor/rules/infra.mdc`.

## New env var checklist

- [ ] `apps/marrow/backend/.env.example` updated
- [ ] `fly secrets set` on `marrow-dev` / `marrow` documented if required
- [ ] Degrades gracefully when missing

## Smoke URLs

There is no dev environment (`api-dev` / `app-dev` are retired). Smoke production after merge to `main`:

- https://api.marrow-health.com/api/v1/health
- https://marrow-health.com/
