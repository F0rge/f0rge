# DevOps Review Playbook

## What this is

Used by the Claude PR review bot when an incoming PR touches infrastructure, CI, Docker, or migrations in `leothesouthafrican/health-tracker`. This is the devops-agent checklist: scan the diff, apply the rules below, return JSON findings. No app-logic review — that's `fastapi-backend` / `frontend-dev`.

## Scope — files YOU review

- `.github/workflows/**`
- `docker-compose*.yml` (currently `docker-compose.dev.yml`, `docker-compose.prod.yml`)
- `backend/Dockerfile`, `backend/docker-entrypoint.sh`
- `backend/migrations/versions/*.py` (migration safety + entrypoint compatibility ONLY — schema/data correctness is `fastapi-backend`)
- `backend/migrations/env.py`, `backend/alembic.ini`
- `frontend/Dockerfile`, `frontend/next.config.*` (only if it affects the build/runtime image)
- Root scripts: `start.sh`, anything top-level executable
- `.dockerignore`, `.gitignore`, `coolify/*` if present
- Anything that affects Pi deployment, Coolify config, Cloudflare tunnel, CI workflow
- NOT app code under `backend/app/**` or `frontend/app/**`, `frontend/components/**`

## Hard rules — instant block findings

- **Migration added without RUN_MIGRATIONS path verified.** Any PR that adds a file under `backend/migrations/versions/` MUST:
  1. Leave `backend/docker-entrypoint.sh` intact (still runs `uv run alembic upgrade head` when `RUN_MIGRATIONS=1`).
  2. Keep `RUN_MIGRATIONS=1` set on the `backend` service in BOTH `docker-compose.dev.yml` AND `docker-compose.prod.yml`.
  3. NOT set `RUN_MIGRATIONS` on `mcp-server` or `embedding-worker` (they share the image; three concurrent `alembic upgrade head` calls race for DDL locks).
  4. If the migration requires a new env var (precedent: migration 004 needs `HEALTHTRACKER_RO_PASSWORD`), it must be present on the `backend` service env block. Cites: `devops/deploy_migration_entrypoint.md`, `qa-engineer/migrations_not_auto_run.md`.

- **Coolify bind-mount path materialization.** Coolify's dockercompose build-pack does NOT do a full repo checkout into `/data/coolify/applications/<uuid>/` — only paths referenced as compose bind-mount sources are materialized on the Pi. New scripts that the running container needs must be `COPY`'d into the image in the Dockerfile, NOT bind-mounted from a repo path. Block any compose change that introduces a bind-mount source pointing at a non-script-volume repo path. Cite: `devops/deploy_migration_entrypoint.md` (Caveats), `health-tracker-backup-strategy-2026-05-17.md`.

- **Single-replica backend assumption.** Block any PR that scales the `backend` service replicas > 1 (e.g. adds `deploy.replicas:` or `scale:`) without simultaneously moving alembic out of the entrypoint into an init container / one-shot migration job. Cite: `devops/deploy_migration_entrypoint.md`.

- **Port collisions on the Pi.** Block any new host port in 8000–8006 without verification: `ssh leo@rpi "sudo ss -tlnp | grep ':80[0-9][0-9]\\s'"`. Known taken: 8000 (Coolify), 8005 (`entre-nos` backend). Health-tracker convention: backend host 8007 → container 8005 for MCP; dev stack uses 8104 (backend), 8107 (MCP), 3104 (frontend). Cite: `project_mcp_phase_2_2c_infra.md`, `health-tracker/CLAUDE.md`.

- **`mem_limit:` legacy v2 style only.** `docker-compose.prod.yml` uses `mem_limit:` consistently (postgres, postgres-backup, backend, mcp-server 256m, embedding-worker 512m). Block any new service that uses `deploy.resources.limits.memory:` instead. Match the existing style block. Cite: `project_mcp_phase_2_2c_infra.md`.

- **DDL with bound parameters in migrations.** `ALTER ROLE ... PASSWORD $1` is rejected by Postgres via asyncpg. Block any migration using bound params in DDL password clauses; require SQL-escaped (`'` → `''`) f-string embedding when value comes from a trusted env var. Cite: `project_mcp_migrations.md`.

- **`GRANT CONNECT ON DATABASE current_database()`** is invalid SQL (`current_database()` is a function, not an identifier). Must be wrapped in a `DO $$ ... $$` block using `EXECUTE format('GRANT CONNECT ON DATABASE %I TO ...', current_database())`. Block any migration that violates this. Cite: `project_mcp_migrations.md`.

- **`DO $$ ... $$` blocks with bound params.** They do not accept bind parameters at all. Inside the block use `format()` + `%I` for identifiers. Cite: `project_mcp_migrations.md`.

- **No `--no-verify` / no `--no-gpg-sign`** in any workflow step, commit, or script. Cite: global `CLAUDE.md` Boundaries.

- **No secret leaks in workflow logs.** Block any workflow step that echoes a `${{ secrets.* }}` value, writes it to a file uploaded as artifact, or passes it on a command line where GitHub's masker can't catch it. Use `env:` blocks.

- **CI workflows trigger on `[develop, main]` only.** `.github/workflows/ci-develop.yml` and `.github/workflows/ci-main.yml` exist; new lint/test/build workflows must scope `on.push.branches` and `on.pull_request.branches` to these two. Cite: `health-tracker/CLAUDE.md` Environments.

- **Multi-stage Dockerfile required for new images.** Builder → production stages, pinned base image versions (no `:latest`). New images need a sibling `.dockerignore` excluding at minimum `.git`, `node_modules`, `.venv`, `.env`, `__pycache__`.

- **`/health` endpoint on every new container-exposed service.** Cite: global devops agent.

- **No direct `docker compose up` on the Pi.** Deploys go through Coolify (manual webhook for health-tracker: `https://coolify.taxpilot.lu/webhooks/source/github/events/manual`). Block any script or doc change that instructs `docker compose up -d` against the Pi.

- **Cloudflare tunnels never point directly at containers.** All ingress goes through the Pi's reverse proxy (Traefik / file-mode cloudflared config); block any tunnel config change that hits a container IP/name.

## Class-of-bug audit (grep before approving)

When the diff matches, cross-check the listed siblings:

- **Adds a migration** (`backend/migrations/versions/*.py`) → verify `backend/docker-entrypoint.sh` unchanged-or-equivalent; both compose files have `RUN_MIGRATIONS=1` on `backend` only; alembic `env.py` and `down_revision` chain still valid.
- **Adds an env var to one compose file** → check `.env.example` updated; the OTHER compose file also has it (dev + prod must match shape, even if values differ); flag a follow-up to add it to the Coolify env UI for both project UUIDs.
- **Adds an exposed host port** → grep all `docker-compose*.yml` for the same port; cross-ref Pi via `ss -tlnp`.
- **Adds a new service** → multi-stage Dockerfile? `/health` endpoint? `mem_limit:`? `env_file: [.env]` + inline `environment:` style? Does it share `backend/Dockerfile`? If yes, must NOT set `RUN_MIGRATIONS`.
- **Touches `docker-entrypoint.sh`** → confirm transparent-passthrough path (env var unset → `exec "$@"`); confirm fail-fast on `alembic upgrade head` non-zero exit.

## Coolify-specific gotchas

- **Project UUIDs** (commit to memory):
  - Health Tracker Dev: `lunthdq8rqd0ad3hi6gcoac0`
  - Health Tracker (prod): `mk404cskowkgcow48g8s8okw`
- **Webhook URL**: `https://coolify.taxpilot.lu/webhooks/source/github/events/manual` (one per repo, HMAC-signed via `applications.manual_webhook_secret_github`)
- **Branch → project mapping**: `develop` → dev project, `main` → prod project. Coolify matches by `git_repository LIKE '%health-tracker%' AND git_branch = <pushed branch>`.
- **Env vars set in the Coolify UI override `.env` file values.** If the PR changes a value in `.env.example`, surface a follow-up to update both Coolify project UIs.
- **Container names rotate per deploy**: `<service>-<project-uuid>-<deployId>`. Always resolve via `docker ps --format '{{.Names}}' | grep '^<service>-<project-uuid>'`.

## Cloudflare / DNS

- **Systemd tunnel ID**: `6c58d6b1-ad4d-4df9-8249-0e2bb88a9c01` (homelab-services, personal CF account)
- **`*.leo-figueiredo.com`** routes live in `/etc/cloudflared/config.yml` on the Pi (mirror at `/home/leo/.cloudflared/config.yml`), file mode. Add new routes BEFORE the catch-all.
- **`*.taxpilot.lu`** routes increasingly in Zero Trust dashboard mode — don't mix patterns for the same zone.
- **Health-tracker subdomains** (all on `leo-figueiredo.com`): `health.`, `health-dev.`, `health-dev-api.`, `health-mcp.`, `health-dev-mcp.`
- **`health-mcp.leo-figueiredo.com`** manual CF setup may still be pending per `project_mcp_phase_2_2c_infra.md` — flag if a PR depends on it without confirming DNS resolves.

## CI workflow standards

- `concurrency:` block on every workflow with `cancel-in-progress: true` (per-ref).
- Pin action versions: `@v4` etc, never `@main` or `@latest`.
- `timeout-minutes:` set on every job (15–30 typical for this repo's lint/test/build).
- Python: `astral-sh/setup-uv@v3` with `enable-cache: true`.
- Node: `actions/setup-node@v4` with `cache: 'npm'` and `cache-dependency-path: frontend/package-lock.json`.
- Runner: `ubuntu-latest` unless platform-specific need.
- `defaults.run.working-directory:` when all steps target the same subdir.

## Post-deploy verification recipe

When a PR with migrations or env-var changes merges, attach this checklist to the review:

```bash
# 1. Watch CI
gh run watch

# 2. After Coolify auto-redeploys, find rotating container names
ssh leo@rpi "docker ps --format '{{.Names}}' | grep -E '^(backend|postgres)-(lunthdq8rqd0ad3hi6gcoac0|mk404cskowkgcow48g8s8okw)'"

# 3. Confirm entrypoint ran the migration
ssh leo@rpi "docker logs <new-backend-name> 2>&1 | grep -E 'entrypoint|alembic|Uvicorn'"

# 4. Confirm DB advanced to the new revision
ssh leo@rpi "docker exec <new-postgres-name> psql -U health -d health -c 'SELECT version_num FROM alembic_version;'"
# Must equal the new revision id from backend/migrations/versions/NNN_*.py

# 5. Confirm new env var is in the running container
ssh leo@rpi "docker inspect <new-backend-name> --format '{{range .Config.Env}}{{println .}}{{end}}' | grep <NEW_VAR>"
```

For env-var-only changes: both compose files must be updated AND the Coolify env UI for both project UUIDs.

## What NOT to flag

- `ruff format --check` being OFF in CI workflows — intentional, see the workflow files.
- Commented-out `pytest -m integration` step in `ci-main.yml` — reserved space, intentional.
- `RUN_MIGRATIONS` unset on `mcp-server` / `embedding-worker` — by design (they share the backend image).
- Catalog seeding logic in `app.main.lifespan` running on every boot — idempotent by design.
- `mem_limit:` instead of `deploy.resources.limits.memory:` — required style for this repo.
- Local dev without `RUN_MIGRATIONS=1` (`./start.sh`, `uv run uvicorn`) — entrypoint isn't in that path; expected to run `uv run alembic upgrade head` by hand.

## Tone & output

Return JSON:

```json
{
  "findings": [
    {"severity": "block|warn|nit", "file": "path", "line": 42, "msg": "...", "cites": ["devops/deploy_migration_entrypoint.md"]}
  ],
  "summary": "one-paragraph verdict"
}
```

- Cite the memory file for every finding.
- `block` only for items in "Hard rules". `warn` for class-of-bug audit misses. `nit` for style.
- Be terse. No prose recap of the diff. No emojis.
