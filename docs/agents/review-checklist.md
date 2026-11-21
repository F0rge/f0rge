> Canonical decisions: [`docs/adr/README.md`](../adr/README.md). Follow [P-005](../adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

# PR review checklist

Implementation detail: `docs/agents/rules/nx.md`. Block on the following when reviewing PRs.

## Every review

1. **Class-of-bug audit.** When a fix names a pattern (a category, not a one-off line), the author greps for sibling occurrences and either fixes all of them or opens a tracked follow-up, and says so in the PR. Block if neither.
2. **No mocks at the seam under test.** A test for a service must not monkeypatch that service or its in-module collaborators. Mock only trust boundaries: outbound HTTP/SDKs, the clock, randomness, read-only config.
3. **Git boundaries.** Block `--no-verify`, `--no-gpg-sign`, force-pushes to `main`, PRs targeting any branch other than `main`, deleting branches without explicit user approval, and changes to `.git/config` or `gh auth` state.
4. **Findings format.** Prefix each finding `[block]` (violates a rule here; cannot merge), `[warn]` (fix or ticket) or `[nit]`, with `file:line`, one sentence on the problem and one on the fix, citing the committed rule and inspected evidence. End with a verdict: `GO`, `NO-GO` or `GO with follow-ups`. A diff-only reviewer adds a verification ticket for the live-server checks in `docs/agents/rules/qa-gate.md` and keeps the gate open until they run.

## Instant block

1. **New app/lib without `project.json`** under `apps/**` or `libs/**` that has `package.json`, `pyproject.toml` or a Cargo package manifest. Virtual Cargo workspace manifests follow the [Rust registration rules](../../.github/rust/README.md).
2. **Missing matching `platform:py`, `platform:ts` or `platform:rust` tag** on a registered project (exception: `marrow-ios` — `scope:marrow` only). Rust projects must satisfy the [fixed target and dependency contract](../../.github/rust/README.md); a tag alone does not establish build/test coverage.
3. **A second change detector** — path filters or hand-kept project lists beside the plan job in `ci.yml`. Nx decides what is affected. Do not pass `--projects` to `nx affected` (it is forwarded into the task).
4. **Libs importing apps** — `libs/**` → `apps/` (TS or Python).
5. **OpenAPI drift bypass** — removing `codegen:check`, `marrow-backend:openapi`, or frontend `implicitDependencies: ["marrow-backend"]` without an equivalent graph-aware check.
6. **Browser e2e added to CI** — it is not run in CI for now; reinstating it is Leo's decision. Locally, run Playwright through `npx nx run …:e2e`.
7. **Root `uv.lock`** created or committed.
8. **Pipeline code that only proves an ADR was followed** (provenance, approval, journal, evidence), or a per-App release program or workflow. Releases go through `cd.yml` and the deploy block (P-004, P-048).
9. **Deprecated Nx remote cache packages** (`@nx/s3-cache`, `@nx/gcs-cache`, `@nx/azure-cache`, `@nx/shared-fs-cache`) or GHA restore of `.nx/cache` across machines.

## Soft flags

- Turning off `targetDefaults` cache without justification.
- Hand-written `nx:run-commands` lint/test when `@nx/eslint` / `@nx/vitest` / `@nx/playwright` already infer them.
- New TypeScript project that does not import `eslint/nx-boundaries.mjs`.

## UI kit — instant block

1. **`apps/**` importing `@base-ui/react` or `@mantine/core` / `@mantine/hooks`** — engines belong in `libs/ui` only.
2. **New shadcn primitive under `apps/**/components/ui`** — add to `libs/ui` instead.
3. **New `CompactStepper`-style fork** instead of `@f0rge/ui` `Stepper` (`libs/ui/src/components/ui/stepper.tsx`).
4. **New primitive in `libs/ui` without a Storybook story** — when `libs/ui/.storybook` exists (skip until Storybook is set up).
5. **Brand tokens (`--marrow-*`) inside `libs/ui` TSX** — brand vars live in `libs/ui/src/styles/skins/` only.
