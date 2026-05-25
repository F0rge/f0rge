# Shared Conventions — All Reviewers

Hard rules every reviewing agent must honour, regardless of domain. Block-level findings here apply to backend, frontend, devops, and qa-engineer alike.

## Plans must delegate to sub-agents

If the PR description outlines a multi-step implementation that does NOT name a sub-agent per chunk of work, flag it. Solo plans where the main agent does all the work are not acceptable. See `feedback_plan_delegation.md`.

Exception: trivial single-file edits (typo fix, dep bump, config tweak) — no sub-agent required.

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

- A human has driven the new feature in a live dev server (`./start.sh` locally OR `health-dev.leo-figueiredo.com`).
- The golden path works end-to-end through the UI.
- At least one error path was driven and the UI failed gracefully.
- Backend logs were tailed during the test for hidden 500s.

The PR-review bot CANNOT do this. Its job is to produce a "Verification ticket" — a bulleted checklist the human must run before clicking Merge. See `feedback_qa_e2e_live_server.md`.

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
1. Read `.claude/review-context/<own-name>-playbook.md` before starting.
2. Read `.claude/review-context/_shared/*.md`.
3. Return findings in JSON format (see each playbook for the schema).

When this review system is updated (rare), a single PR refreshes all playbooks from the underlying memory files.

## Branch & PR conventions

- `develop` is the default integration branch.
- PRs land on `develop`, run `.github/workflows/ci-develop.yml`, then merge.
- Promotion to prod is a PR `develop` → `main`, gated by `.github/workflows/ci-main.yml`.
- Feature branches: `feat/<descriptive-name>`, `fix/<descriptive-name>`, `chore/<descriptive-name>`.
- Direct push to `main` is only acceptable for single-file edits on personal config.

## Git workflow boundaries

Block on any PR or workflow step that:
- Uses `--no-verify` (skips hooks).
- Uses `--no-gpg-sign` (bypasses signing).
- Force-pushes to `main` or `develop`.
- Deletes branches without explicit user approval.
- Modifies `.git/config` or `gh auth` state.

## Post-merge hygiene

After this PR merges, the working tree must be clean:
- Worktrees: spawned worktrees must be unlocked, removed, pruned. `git worktree list` shows only `main` (or other intentional trees).
- Branches: `git cleanup` alias removes branches whose remote tracking branch is gone (`: gone]` markers).
- `git status` is clean.
- Session ends on the default branch (`develop`), fast-forwarded to origin.

See global `~/.claude/CLAUDE.md` § "Post-Merge Hygiene".

## Required environment vars must mirror to `.env.example`

Every new `Settings` attribute in `backend/app/config.py` requires:
1. A matching line in `backend/.env.example`.
2. If required (no safe default), documentation of how to obtain the value.
3. For deployed environments: a follow-up to set it in the Coolify env UI for both project UUIDs.

Block on missing `.env.example` entry. See `mcp_server_issue_49_findings.md`.
