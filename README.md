# f0rge

Personal Nx monorepo. Home to **marrow** (daily health check-in) and **dk tag printer** (DasKasas price tags).

## Structure

```
libs/
├── backend/
│   ├── core/       f0rge-core     exceptions + handler registration
│   ├── db/         f0rge-db       engine/session/RLS/CRUD factories
│   ├── storage/    f0rge-storage  object storage + image resize
│   └── testing/    f0rge-testing  testcontainer + savepoint fixtures
└── ui/             @f0rge/ui      shadcn primitives, API client, hooks

apps/marrow/
├── backend/   FastAPI + async SQLAlchemy + Postgres (Fly MPG) — Python 3.10, uv
└── frontend/  Next.js 16 + React 19 + Tailwind + @f0rge/ui

apps/dk/tag-printer/
├── backend/   FastAPI + pandas/fpdf — Python 3.10, uv (Pi Coolify prod)
└── frontend/  Next.js 16 + React 19 + Tailwind 3
```

Agent workflow, environments, conventions, and sub-agent delegation rules live in [AGENTS.md](AGENTS.md). Deploy conventions: [`.cursor/rules/infra.mdc`](.cursor/rules/infra.mdc), [`.github/deploy/README.md`](.github/deploy/README.md).

## Nx workspace

Nine application/library projects: `marrow-backend`, `marrow-frontend`, `dk-tag-printer-backend`, `dk-tag-printer-frontend`, `f0rge-core`, `f0rge-db`, `f0rge-storage`, `f0rge-testing`, `f0rge-ui`. Frontend targets (`build`/`dev`/`start`) are inferred by the `@nx/next` plugin; backend targets (`lock`/`sync`) by `@nxlv/python`. `defaultBase` is `develop`.

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

- **`CI (develop)` / `CI (main)`** — single pipeline per branch: `detect` → `backend` / `frontend` (Nx affected) → `ci` gate → `deploy` (push only). The `ci` job is the required branch check (`main-pr-gate` on `main`). Detection is tag-driven: `backend` for `platform:py`, `frontend` for `platform:ts`. Every new project must carry the matching `platform:` tag in its `project.json` or CI will silently ignore it.
- **Deploy stage** ([`deploy-reusable.yml`](.github/workflows/deploy-reusable.yml)): reads [`.github/deploy/manifest.yml`](.github/deploy/manifest.yml) + Nx affected → **Fly** (marrow) or **Coolify webhook** (dk tag printer on Pi). Marrow: `deploy api` → `deploy mcp` (serial) → `deploy frontend` → smoke. dk: prod-only on `main` via Coolify secrets.
- **Manual deploy** (skips CI): `gh workflow run "CI (develop)" --ref develop -f component=mcp` (`all` / `api` / `mcp` / `frontend` — marrow Fly only).
