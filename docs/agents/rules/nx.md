> Canonical decisions: [`docs/adr/README.md`](../../adr/README.md). Follow [P-005](../../adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# Nx workspace (f0rge)

Canonical map: `nx.json` + each app/lib `project.json`. Details live there — do not invent alternate CI wiring.

## Required for every new app/lib

A Project that should be released also needs a deploy block; see [the deploy page](../../../.github/deploy/README.md).

1. `project.json` with tags:
   - Python: `platform:py` + `scope:shared|marrow|dk|…`
   - TypeScript: `platform:ts` + matching `scope:`
   - Rust: `platform:rust` + matching `scope:`, with [the Rust target contract](../../../.github/rust/README.md)
   - Exception: `marrow-ios` — `scope:marrow` only (no `platform:` — Linux CI ignores it)
2. Node/Python/Cargo manifests need their matching platform tags. Guard: `.github/scripts/check-nx-projects.sh`; the Rust job also validates every Cargo project before affected selection. Follow [Rust/Nx registration](../../../.github/rust/README.md) for targets, local dependencies and workspace inputs.
3. Never create a root `uv.lock` (`@nxlv/python` flips to workspace mode).

## Cache + targets

- Cache is on via `targetDefaults` in `nx.json` (`lint`, `format-check`, `typecheck`, `test`, `build`, `codegen:check`). Do not disable without reason.
- Initial Rust targets explicitly disable Nx caching until native output restoration and environment fingerprints are proven. Cargo still manages its own local intermediates; `nx affected` still selects projects. This does not authorize remote artifact reuse or a release.
- Prefer inferred targets (`@nx/eslint`, `@nx/vitest`, `@nx/playwright`, `@nx/next`) over new `nx:run-commands` copies.
- Do **not** persist `.nx/cache` across GHA machines. Never add deprecated `@nx/s3-cache` / `@nx/gcs-cache` / `@nx/azure-cache` / `@nx/shared-fs-cache`.

## CI

Pipeline overview: [root `AGENTS.md`](../../../AGENTS.md#cicd).

- `ci.yml` starts with one plan job. It runs the cheap repository guards, then `.github/scripts/plan.mjs` asks Nx what is affected and emits three booleans (Python, TypeScript, Rust) and the matrix of affected Apps with their Host.
- A language job is skipped unless its boolean is true. It runs one `nx affected` invocation, filtered by tag: `npx nx affected -t=lint,format-check,test --exclude='*,!tag:platform:py'`. `affected` does **not** take `--projects` — that flag is forwarded into the task and breaks tsc/ruff.
- After the language jobs pass (a skipped one does not block), one image job per affected App runs the `image` target (defined once in `nx.json` `targetDefaults`, declared as `"image": {}` by each deployable Project) on every deployable Project of that App. The target runs `.github/scripts/image.mjs`, which reads the Project's deploy block to build, start and health-check the image; on `main` it also pushes it. It is not cached. `npx nx run <project>:image` runs the same check locally.
- Nx alone decides what is affected. Do not add a second change detector (path filters, hand-kept project lists).
- On `main`, affected is measured from the last fully successful run, Release included, so an App whose Release failed is built and released again by the next push.
- No nightly run, no run-everything mode, no browser e2e in CI.
- CI workflows in this repo target `main`. Do not open pull requests against `develop`. A remote `develop` ref is not an approved branch. `defaultBase` is `main`. Nx is the current monorepo tool, not a newly selected build orchestrator.

## Boundaries + OpenAPI + e2e

- TS imports: `@nx/enforce-module-boundaries` via `eslint/nx-boundaries.mjs`. This sentence is not a full inventory of that file: it also names `scope:firstout` and `scope:daskasas`, and it does not name `scope:buycycle` or `scope:envmon`. Do not edit the ESLint file from an instruction-only change.
- Python libs→apps: keep `.github/scripts/check-lib-boundary.sh` (ESLint does not see Python).
- Marrow OpenAPI: `marrow-frontend` has `implicitDependencies: ["marrow-backend"]` and `codegen:check` (depends on `marrow-backend:openapi`). Do not replace with ad-hoc CI export+diff steps.
- Playwright: `npx nx run marrow-frontend:e2e` (inferred), run locally against a running stack. CI does not run it.

## Python plugin

- `@nxlv/python` with `inferDependencies: true` and `sync.globalGenerators: ["@nxlv/python:pkg-sync"]`.
- Keep per-project `uv.lock`. Run `npx nx sync:check` when changing local path deps.

See also `docs/agents/review-checklist.md` (PR review) and `docs/agents/rules/shared-libs.md`.
