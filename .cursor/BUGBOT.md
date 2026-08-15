# Bugbot / Agent Review — f0rge Nx gates

Implementation detail: `.cursor/rules/nx.mdc`. Block on the following when reviewing PRs.

## Instant block

1. **New app/lib without `project.json`** under `apps/**` or `libs/**` that has `package.json` or `pyproject.toml` (exception: documented radar/demo WIP without manifests).
2. **Missing `platform:py` or `platform:ts` tag** on a new/edited `project.json` (exception: `marrow-ios` — `scope:marrow` only).
3. **Custom CI detect / project-list plumbing** — reintroducing `nx show projects --affected` into a detect job that feeds `run-many --projects "$LIST"`. Prefer `nx affected -t=… --exclude='*,!tag:platform:…'`. Do not pass `--projects` to `nx affected` (it is forwarded into the task).
4. **Libs importing apps** — `libs/**` → `apps/` (TS or Python).
5. **OpenAPI drift bypass** — removing `codegen:check`, `marrow-backend:openapi`, or frontend `implicitDependencies: ["marrow-backend"]` without an equivalent graph-aware check.
6. **Playwright outside Nx** — new/changed CI that runs `npx playwright test` instead of `npx nx run …:e2e`.
7. **Root `uv.lock`** created or committed.
8. **Deprecated Nx remote cache packages** (`@nx/s3-cache`, `@nx/gcs-cache`, `@nx/azure-cache`, `@nx/shared-fs-cache`) or GHA restore of `.nx/cache` across machines.

## Soft flags

- Turning off `targetDefaults` cache without justification.
- Hand-written `nx:run-commands` lint/test when `@nx/eslint` / `@nx/vitest` / `@nx/playwright` already infer them.
- New TypeScript project that does not import `eslint/nx-boundaries.mjs`.

## UI kit — instant block

1. **`apps/**` importing `@base-ui/react` or `@mantine/core` / `@mantine/hooks`** — engines belong in `libs/ui` only.
2. **New shadcn primitive under `apps/**/components/ui`** — add to `libs/ui` instead.
3. **New `CompactStepper`-style fork** instead of `@f0rge/ui` `Stepper` (`libs/ui/src/components/ui/stepper.tsx`).
4. **New primitive in `libs/ui` without a Storybook story** — when `libs/ui/.storybook` exists (skip until Storybook is set up).
5. **Brand tokens (`--marrow-*`, `--dk-*`) inside `libs/ui` TSX** — brand vars live in `libs/ui/src/styles/skins/` only.
