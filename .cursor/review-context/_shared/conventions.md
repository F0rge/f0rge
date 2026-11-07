> Canonical decisions: [`docs/adr/README.md`](../../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# Shared Conventions — All Reviewers

Hard rules every reviewing agent must honour, regardless of domain. Block-level findings here apply to backend, frontend, devops, and qa-engineer alike.

## Shared libraries — non-duplication

Apps import from `libs/` — never the reverse. Block on:
- `libs/**` importing from `apps/` or `@/` paths resolving to apps
- App code re-implementing lib-owned helpers (see `.cursor/rules/shared-libs.mdc`)
- New projects missing `platform:` / `scope:` tags in `project.json`
- Creating a root `uv.lock` (breaks per-project lock isolation)

See `AGENTS.md` § Shared libraries for the canonical inventory. **Nx gates** (affected CI, OpenAPI `codegen:check`, Playwright via Nx, project registration): `.cursor/rules/nx.mdc` and `.cursor/BUGBOT.md` — do not duplicate the checklist here.

## Plans must delegate to sub-agents

**At planning time** (before any code), every implementation plan MUST include a sub-agent map: one named sub-agent from `~/.cursor/agents/` per work chunk, with deliverable and dependencies. The planning agent orchestrates; it does not implement the chunks. See `.cursor/rules/orchestration.mdc`. `.cursor/skills/ship-feature/SKILL.md` is not in this repo; do not invent it.

At PR review time: if the PR description outlines multi-step work that does NOT name a sub-agent per chunk, flag it. Solo plans where the main agent did all the work are not acceptable.

Exception: trivial single-file edits (typo fix, dep bump, config tweak) — one specialist sub-agent or inline edit is fine.

## Audit class of bug before declaring fixed

When a PR fixes a *named pattern* (a category, not a one-off line):

1. The author must grep the codebase for sibling occurrences.
2. The author must either (a) fix every sibling in this PR, OR (b) open a tracked follow-up issue.
3. The PR description must mention the audit.

If neither — block. Two prod outages on 2026-05-17 were caused by missing this step (entries.entry_time fixed, photos.meal_time missed). See `feedback_audit_class_of_bug.md`.

Common patterns that warrant an audit:
- tz-aware → tz-naive column binding
- `.scalar_one_or_none()` on non-unique WHERE
- `field || undefined` + Pydantic `exclude_unset=True`
- Unstable `useEffect` deps including a `useMutation` callback
- `'use client'` page reading localStorage in `useState` initializer
- DDL with bound params
- `field_validator` missing `mode="after"`

## Live-server gate (acceptance criteria)

Automated checks (lint, pytest, build, typecheck) are NOT a complete gate. The PR is not done until:

- A human has driven the new feature in a live dev server (`uvicorn` + `npm run dev` locally OR the live app after merge).
- The golden path works end-to-end through the UI.
- At least one error path was driven and the UI failed gracefully.
- Backend logs were tailed during the test for hidden 500s.

A diff-only reviewer CANNOT do this. Its job is to produce a "Verification ticket" — a bulleted checklist the human must run before clicking Merge. See `feedback_qa_e2e_live_server.md`.

## No mocks at the seam under test

Tests for `app.services.X` must NOT monkeypatch `app.services.X` or its in-module collaborators. Mocks belong at trust boundaries only:
- Outbound HTTP (`httpx`, OpenAI/OpenRouter SDK, anthropic, AWS)
- Clock (`datetime.now()`)
- Randomness (`random`, `secrets.token_*`)
- Read-only config

If a test's seam is mocked, the test cannot catch the bugs that mock seam was designed to catch. See `feedback_no_mocks_at_seam_under_test.md`.

## Thin routers

FastAPI routers are 1-3 lines: signature, single service-call delegation, return. No `if`, no `raise`, no `try`, no `db.query`, no helpers in the router module. Pre-existing violations are NOT this PR's problem — only flag NEW ones. See `feedback_thin_routers.md`.

## Sub-agents must read/write their own memory

When invoked, each sub-agent must:
1. Read `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting; write back gotchas when done.
2. Read `.cursor/review-context/<own-name>-playbook.md` and `.cursor/review-context/_shared/*.md` when doing PR review.
3. Return review findings in JSON format (see each playbook for the schema).

Canonical playbooks: `.cursor/review-context/`.

## Branch & PR conventions

- Trunk-based: pull requests go to `main`. A remote `develop` ref may still exist; block any PR targeting it. It is not an approved long-lived branch.
- Short-lived branches off `main`: `feat/…`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`, `test/…`, `hotfix/…`.
- PRs into `main` only, `.github/workflows/ci.yml` green, squash merge after review. A merge is not Leo's production release approval. Do not enable auto-merge.
- Hotfixes are ordinary PRs into `main`.
- Do not direct-push to `main`. A personal-config exception is not a production release approval.

## Git workflow boundaries

Block on any PR or workflow step that:
- Uses `--no-verify` (skips hooks).
- Uses `--no-gpg-sign` (bypasses signing).
- Force-pushes to `main`.
- Deletes branches without explicit user approval.
- Modifies `.git/config` or `gh auth` state.

## Post-merge hygiene

After this PR merges, the working tree must be clean:
- Worktrees: spawned worktrees must be unlocked, removed, pruned. `git worktree list` shows only `main` (or other intentional trees).
- Branches: `git cleanup` alias removes branches whose remote tracking branch is gone (`: gone]` markers).
- `git status` is clean.
- Session ends on the default branch (`main`), fast-forwarded to origin.

See global `~/.cursor/rules/leo-system-wide.mdc` § "Post-Merge Hygiene".

## Required environment vars must mirror to `.env.example`

Every new `Settings` attribute in `apps/marrow/backend/app/config.py` requires:
1. A matching line in `apps/marrow/backend/.env.example`.
2. If required (no safe default), documentation of how to obtain the value.
3. Do not run `fly secrets set` or change production secrets from this checklist. A production secret change needs a separate explicit approval.

Block on missing `.env.example` entry. See `mcp_server_issue_49_findings.md`.
