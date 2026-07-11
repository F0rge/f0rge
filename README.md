# f0rge

Personal Nx monorepo. Currently home to **marrow** (daily health check-in app).

## Structure

```
apps/marrow/
├── backend/   FastAPI + async SQLAlchemy + Postgres (Fly MPG) — Python 3.10, uv
└── frontend/  Next.js 16 + React 19 + Tailwind + shadcn/ui
```

Agent workflow, environments, conventions, and sub-agent delegation rules live in [AGENTS.md](AGENTS.md). Fly deploy conventions: [`.cursor/rules/infra.mdc`](.cursor/rules/infra.mdc).

## Nx workspace

Two projects: `marrow-backend`, `marrow-frontend`. Frontend targets (`build`/`dev`/`start`) are inferred by the `@nx/next` plugin; backend targets (`lock`/`sync`) by `@nxlv/python`. `defaultBase` is `develop`.

```bash
npx nx graph                                   # interactive dependency graph (opens a browser)
npx nx graph --file=graph.html                 # same, written to a static file instead
npx nx show projects                           # list projects
npx nx run marrow-backend:lint                 # ruff check
npx nx run marrow-backend:test                 # pytest
npx nx run marrow-frontend:lint                # eslint
npx nx run marrow-frontend:typecheck           # tsc --noEmit
npx nx run marrow-frontend:build               # production build
npx nx run-many -t lint test typecheck         # everything, across both projects
npx nx affected -t lint test typecheck         # only what changed vs. develop
npx nx reset                                   # clear the Nx cache
```

## CI/CD

- **`CI (develop)` / `CI (main)`** — parallel `backend` and `frontend` jobs when Nx affected; aggregate `ci` job is the required branch check (`main-pr-gate` on `main`). Detection is tag-driven: the `backend` job runs for affected projects tagged `platform:py`, `frontend` for `platform:ts`. Every new project must carry the matching `platform:` tag in its `project.json` or CI will silently ignore it.
- **`Fly Deploy (develop)` / `Fly Deploy (main)`** — triggered after a green CI push (`workflow_run`). Reusable workflow jobs:
  - `plan` → `deploy api` → `deploy mcp` (serial, migrations via API `release_command`) → `deploy frontend` (parallel with MCP)
  - `smoke` — health curls for components that deployed
- **Manual dispatch** — redeploy one component: `gh workflow run "Fly Deploy (develop)" --ref develop -f component=mcp` (`all` / `api` / `mcp` / `frontend`).
- **Note:** `workflow_run` deploy workflows execute from the repo default branch (`main`); merge workflow changes to `main` before automated prod deploys pick them up.
