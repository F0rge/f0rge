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

Ten projects: `marrow-backend`, `marrow-frontend`, `marrow-ios`, `dk-tag-printer-backend`, `dk-tag-printer-frontend`, `f0rge-core`, `f0rge-db`, `f0rge-storage`, `f0rge-testing`, `f0rge-ui`. Inferred targets: Next (`build`/`dev`/`start`), ESLint (`lint`), Vitest (`test`), Playwright (`e2e`), `@nxlv/python` (`lock`/`sync` + import graph). Task cache via `targetDefaults` in `nx.json`. `defaultBase` is `develop`. Conventions: [`.cursor/rules/nx.mdc`](.cursor/rules/nx.mdc).

```bash
npx nx graph                                   # interactive dependency graph
npx nx show projects                           # list projects
npx nx run marrow-backend:lint                 # ruff check
npx nx run marrow-backend:test                 # pytest
npx nx run marrow-frontend:lint                # eslint (inferred)
npx nx run marrow-frontend:typecheck           # tsc --noEmit
npx nx run marrow-frontend:build               # production build
npx nx run marrow-frontend:e2e                 # Playwright
npx nx run marrow-frontend:codegen:check       # OpenAPI drift (depends on backend:openapi)
npx nx run marrow-ios:codegen                  # Swift client (local Xcode)
npx nx affected -t lint typecheck build        # only what changed vs. develop
npx nx run-many -t lint test typecheck         # everything
npx nx sync:check                              # Python pkg-sync
npx nx reset                                   # clear the Nx cache
```

## CI/CD

- **`CI`** ([`ci.yml`](.github/workflows/ci.yml)) — parallel `backend` / `frontend` jobs each run `nx affected` filtered with `--exclude='*,!tag:platform:py|ts'` (no detect job) → `ci` gate. Required checks: `ci` on `develop`; `ci` + `playwright smoke` on `main` (see [`.github/branch-rules.md`](.github/branch-rules.md)). Every new project must carry a `platform:` tag or CI ignores it (guard: [`.github/scripts/check-nx-projects.sh`](.github/scripts/check-nx-projects.sh)).
- **`Deploy`** ([`deploy.yml`](.github/workflows/deploy.yml)) — separate workflow after successful CI on push to `develop`/`main`. Orchestrator ([`deploy-reusable.yml`](.github/workflows/deploy-reusable.yml)): manifest + Nx affected → Railway smoke (marrow) or Coolify webhook (dk). Marrow: Railway autodeploy + Actions smoke. dk: prod-only on `main` via Coolify.
- **Manual deploy**: `gh workflow run Deploy --ref develop -f environment=develop -f component=mcp` (`all` / `api` / `mcp` / `frontend` — marrow only).
