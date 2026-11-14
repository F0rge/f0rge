# F0rge

Personal Nx monorepo. Each app owns its business rules and data; reusable infrastructure lives in `libs/`.

## Structure

| Area | Source | Nx projects |
|---|---|---|
| Marrow health check-in | `apps/marrow/` | `marrow-backend`, `marrow-frontend`, `marrow-ios` |
| Firstout back office | `apps/firstout/` | `firstout-backend`, `firstout-frontend` |
| DasKasas storefront | `apps/storefront/` | `daskasas-commerce`, `daskasas-web` |
| DasKasas tag printer | `apps/dk/tag-printer/` | `dk-tag-printer-backend`, `dk-tag-printer-frontend` |
| Buycycle dashboards | `apps/buycycle/` | `buycycle` |
| Environment Monitor | `apps/environment-monitor/` | `environment-monitor-backend`, `environment-monitor-frontend` |
| Workflow orchestration | `apps/airflow/` | `airflow` |
| Shared backend packages | `libs/backend/{core,db,storage,testing}/` | `f0rge-core`, `f0rge-db`, `f0rge-storage`, `f0rge-testing` |
| Shared legacy UI kit | `libs/ui/` | `f0rge-ui` |

The 18 registered projects include existing Python, Next.js, Medusa, Swift, and sensor/dashboard apps. New apps follow [the canonical ADRs](docs/adr/README.md); those decisions do not migrate the existing apps automatically.

Agent workflow, environments, conventions, and sub-agent delegation rules live in [AGENTS.md](AGENTS.md). Deploy conventions: [`.cursor/rules/infra.mdc`](.cursor/rules/infra.mdc), [`.github/deploy/README.md`](.github/deploy/README.md).

## Nx workspace

Project names and tags live in each `project.json`. Inferred targets cover Next, ESLint, Vitest, Playwright, and Python dependency graphs. Task caching is configured in `nx.json`, with `main` as the default base. See [Nx conventions](.cursor/rules/nx.mdc).

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

- **CI** ([`ci.yml`](.github/workflows/ci.yml)) runs affected lint, type, test and build checks. Required checks are `ci` and `playwright smoke` on PRs to `main`; see [branch rules](.github/branch-rules.md).
- **Release hold:** the existing **Deploy** workflow is disabled. This proposed change replaces its source with manual preparation and makes the historical reusable entry point fail without deployment. Neither workflow calls a provider, uses deployment credentials or runs production smoke. [The manifest](.github/deploy/manifest.yml) remains historical target inventory; DasKasas has separate Railway configuration outside it.
- **Protection and remaining work:** the GitHub `production` environment is configured, but it does not protect direct Railway/Coolify operations. Runtime provider state has not been checked for this change. Tested immutable artifact promotion, deployment-secret migration and an independent automation/approval identity remain future work; the proposed workflow protection has not been exercised. See [release guidance](.github/deploy/README.md) before activation.
- **Production control:** Leo approves every production release. Green CI, a merge and environment configuration do not grant that approval. Preserve the hold and verify the exact target before any separately authorized deployment.
