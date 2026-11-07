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

- **MPG role DDL on Fly (historical inventory).** Older notes say `FLY_MPG_SKIP_ROLE_DDL=1` and `fly mpg users create`. Do not run those commands. Creating roles or changing production database access needs a separate explicit approval. It is not part of reviewing this file.

- **Secrets in repo.** Block any hardcoded `FLY_API_TOKEN`, database passwords, or JWT secrets.

- **Custom domain certificates (historical inventory).** Older notes mention `fly certs add` and Cloudflare DNS changes for `marrow-health.com`. Do not change DNS or certificates from this playbook. A new hostname still needs Leo's approval under the ADR domain rule, as a separate operation.

## Fly deploy conventions (historical inventory, not a live check and not a release approval)

| Env | Branch | Apps | Workflow |
|---|---|---|---|
| Prod | `main` | `marrow`, `marrow-mcp`, `marrow-ui` | older `ci.yml` deploy job |

This table is historical inventory. It is not the current workflow and not permission to deploy. Older notes describe API then MCP, with frontend in parallel, alembic via `release_command`, jobs named `plan`, `deploy api`, `deploy mcp`, `deploy frontend`, and `smoke`, plus `workflow_dispatch` component choices. They also name MPG cluster `nlkxjo5m3240y93v` and databases `marrow` and `marrow_dev`. Do not treat `marrow_dev` as a current branch or as permission to provision it.

Full reference: [README.md](../../README.md#cicd), `.cursor/rules/infra.mdc`.

## New env var checklist

- [ ] `apps/marrow/backend/.env.example` updated
- [ ] Do not run `fly secrets set`. Production secret changes are a separate explicit approval, not a checklist step.
- [ ] Degrades gracefully when missing

## Smoke URLs

Hostnames `api-dev` and `app-dev` are described as retired names. Do not smoke production after a merge. A production smoke is a separately authorized operation, not an automatic next step, and a merge is not Leo's release approval:

- https://api.marrow-health.com/api/v1/health
- https://marrow-health.com/
