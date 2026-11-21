# F0rge

Personal Nx monorepo. Each app owns its business rules and data; reusable infrastructure lives in `libs/`.

## Structure

| Area | Source | Nx projects |
|---|---|---|
| Marrow health check-in | `apps/marrow/` | `marrow-backend`, `marrow-frontend`, `marrow-ios` |
| Firstout back office | `apps/firstout/` | `firstout-backend`, `firstout-frontend` |
| DasKasas storefront | `apps/storefront/` | `daskasas-commerce`, `daskasas-web` |
| DasKasas tag printer | `apps/dk/tag-printer/` | `dk-tag-printer-backend`, `dk-tag-printer-frontend` |
| Environment Monitor | `apps/environment-monitor/` | `environment-monitor-backend`, `environment-monitor-frontend` |
| Workflow orchestration | `apps/airflow/` | `airflow` |
| Shared backend packages | `libs/backend/{core,db,storage,testing}/` | `f0rge-core`, `f0rge-db`, `f0rge-storage`, `f0rge-testing` |
| Shared legacy UI kit | `libs/ui/` | `f0rge-ui` |

The registered projects include existing Python, Next.js, Medusa, Swift, and sensor/dashboard apps. New apps follow [the canonical ADRs](docs/adr/README.md); those decisions do not migrate the existing apps automatically.

Agent workflow, environments, conventions, and sub-agent delegation rules live in [AGENTS.md](AGENTS.md). Deploy conventions: [`docs/agents/rules/infra.md`](docs/agents/rules/infra.md), [`.github/deploy/README.md`](.github/deploy/README.md).

## Nx workspace

Project names and tags live in each `project.json`. Inferred targets cover Next, ESLint, Vitest, Playwright, and Python dependency graphs. Task caching is configured in `nx.json`, with `main` as the default base. See [Nx conventions](docs/agents/rules/nx.md).

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
npx nx affected -t lint typecheck build        # only what changed vs. main
npx nx run-many -t lint test typecheck         # everything
npx nx sync:check                              # Python pkg-sync
npx nx reset                                   # clear the Nx cache
```

## CI/CD

- **CI** ([`ci.yml`](.github/workflows/ci.yml)) builds and tests only what a change affects, routed by language, and builds one Artifact per deployable Project. `merge-gate` is the single required check on PRs to `main`; see [branch rules](.github/branch-rules.md).
- **CD** ([`cd.yml`](.github/workflows/cd.yml)) runs as the last job of CI on `main` and releases every affected App to its Host with the Artifacts CI just built. A failed Release puts each service back on the image it ran before.
- Each deployable Project names its Host and services in the deploy block of its `project.json`. Manual Releases, rollbacks and accepted ceilings: [`.github/deploy/README.md`](.github/deploy/README.md). Terms: [Delivery glossary](.github/CONTEXT.md). Policy: [P-006](docs/adr/governance.md#p-006).
