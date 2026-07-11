# DevOps Review Playbook

## What this is

Used by the PR review bot when an incoming PR touches infrastructure, CI, Docker, Fly deploy, or migrations. Scan the diff, apply the rules below, return JSON findings.

## Scope — files YOU review

- `.github/workflows/**`
- `**/fly*.toml`
- `backend/Dockerfile`, `backend/docker-entrypoint.sh`
- `backend/migrations/versions/*.py` (migration safety + deploy compatibility ONLY)
- `backend/migrations/env.py`, `backend/alembic.ini`
- `frontend/Dockerfile`, `frontend/next.config.*`
- Root scripts: `start.sh`, `scripts/fly-*.sh`
- `.dockerignore`, `.gitignore`
- Anything affecting Fly apps, MPG, Cloudflare DNS (`marrow-health.com`), CI workflows
- NOT app code under `backend/app/**` or `frontend/app/**`

## Hard rules — instant block findings

- **Migration added without Fly release_command path.** Any PR adding `backend/migrations/versions/` MUST leave `[deploy] release_command` in `fly.toml` / `fly.prod.toml` running `alembic upgrade head` via `MIGRATION_DATABASE_URL`. Runtime `DATABASE_URL` stays least-privilege (`healthtracker-app`).

- **MPG role DDL on Fly.** Set `FLY_MPG_SKIP_ROLE_DDL=1` on Fly apps; roles are provisioned via `fly mpg users create`, not migration-side DDL on Fly.

- **Secrets in repo.** Block any hardcoded `FLY_API_TOKEN`, database passwords, or JWT secrets.

- **Custom domain without cert plan.** New `marrow-health.com` hostnames need `fly certs add` + Cloudflare DNS-only (grey cloud) + ACME CNAME until issued.

## Fly deploy conventions

| Env | Branch | Apps | Workflow |
|---|---|---|---|
| Dev | `develop` | `marrow-dev`, `marrow-mcp-dev`, `marrow-ui-dev` | `fly-deploy-develop.yml` |
| Prod | `main` | `marrow`, `marrow-mcp`, `marrow-ui` | `fly-deploy-main.yml` |

Deploy order: API (alembic via `release_command`) → MCP → frontend.

MPG cluster: `d1zj5omzqwvryqkv` (`marrow-db-prod`). Databases: `marrow` (prod), `marrow_dev` (dev).

Full reference: `docs/fly-cutover-runbook.md`, `.cursor/rules/infra.mdc`.

## New env var checklist

- [ ] `backend/.env.example` updated
- [ ] `fly secrets set` on `marrow-dev` / `marrow` documented if required
- [ ] Degrades gracefully when missing

## Smoke URLs (dev)

- https://api-dev.marrow-health.com/api/v1/health
- https://app-dev.marrow-health.com/
