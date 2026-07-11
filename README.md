# f0rge

Personal Nx monorepo. Currently home to **marrow** (daily health check-in app).

## Structure

```
apps/marrow/
├── backend/   FastAPI + async SQLAlchemy + Postgres (Fly MPG) — Python 3.10, uv
└── frontend/  Next.js 16 + React 19 + Tailwind + shadcn/ui
```

Agent workflow, environments, conventions, and sub-agent delegation rules live in [AGENTS.md](AGENTS.md). Deploy runbook and architecture references live in [docs/](docs/).

## Running locally

```bash
./start.sh                                                                    # both services
cd apps/marrow/backend && uv run uvicorn app.main:app --port 8000 --reload    # backend only
cd apps/marrow/frontend && npm run dev                                        # frontend only
```

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

- `ci-develop.yml` / `ci-main.yml` — lint + test + build gates on PRs into `develop` / `main`
- `fly-deploy-*.yml` — auto-deploy to Fly after CI is green
