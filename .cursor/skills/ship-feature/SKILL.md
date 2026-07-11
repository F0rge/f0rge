---
name: ship-feature
description: Plan and ship a feature or fix end-to-end from a short prompt or GitHub issue. Delegates to repo sub-agents, runs QA, opens PR to develop, waits for CI, merges, smoke-tests dev, opens PR to main, waits for CI, then asks for final review. Use when the user says ship feature, implement issue, /ship-feature, plan and implement, or pastes a GitHub issue URL.
---

# Ship Feature — Idea/Issue → Develop → Dev Smoke → Main PR

Orchestrator workflow for health-tracker. Read `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/orchestration.mdc`, and `~/.cursor/rules/leo-system-wide.mdc` before starting.

**Intake:** either a GitHub issue (`gh issue view N`) or a short user prompt. Turn prompts into a one-paragraph problem statement + acceptance criteria before planning.

**Gates:** stop for user approval after Phase 1 (plan). All later phases run autonomously unless blocked.

---

## Phase 0 — Bootstrap

1. `git fetch origin && git checkout develop && git pull origin develop`
2. Branch: `feat/<slug>` or `fix/<slug>` from `develop`
3. Read `~/.cursor/agent-memory/*/MEMORY.md` index files referenced from project memory

---

## Phase 1 — Plan (delegation mandatory)

1. **Research** (right-sized): `Explore` for codebase; WebSearch only when external pattern unclear
2. **Q&A**: 0–4 questions via AskQuestion only for genuine ambiguity
3. **Draft plan** using [references/plan-template.md](references/plan-template.md)

Non-negotiable plan sections:

- Context (why, user-visible outcome)
- **Sub-agent map** — every chunk names a sub-agent from `~/.cursor/agents/` (see `.cursor/rules/orchestration.mdc`)
- Critical files (new + modified)
- Verification plan (local E2E + dev-env smoke steps)
- Open items needing sign-off

4. **Hand off** — present plan; do not implement until user approves (or says "go")

---

## Phase 2 — Implement

For each row in the sub-agent map:

1. Brief with [references/sub-agent-brief-template.md](references/sub-agent-brief-template.md)
2. Dispatch via Task tool — `composer-2.5` only; parallel when independent
3. Review actual diffs after each return; tighten if brief not met
4. `git diff --stat` vs plan critical-files list when all chunks done

---

## Phase 2.5 — Simplify pass

After all implementation chunks:

1. `git diff --stat HEAD` → baseline
2. Strip single-use abstractions, dead code, out-of-scope edits (or invoke simplify review if available)
3. Re-run unit tests on touched production code if simplify changed logic
4. Record delta for PR body

Do not simplify mid-implementation between sub-agents.

---

## Phase 3 — QA gate (local)

Run `.cursor/rules/qa-gate.mdc` phases. Produce structured **QA Gate Report** with PASS/FAIL per phase.

Minimum automated:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest tests/ -v --tb=short
cd frontend && npm run lint && npm run typecheck && npm run build
```

**Live-server E2E** (mandatory for UI/API user paths): `./start.sh`, auth bypass per qa-gate rule, drive golden path + one error path in browser MCP. pytest alone is not the gate.

If FAIL: fix inline (small) or loop sub-agent (large). Do not open PR until PASS.

---

## Phase 4 — PR to develop

1. Commit in coherent units; message style from recent `git log`
2. `git push -u origin HEAD`
3. `gh pr create --base develop` with body from [references/pr-body-template.md](references/pr-body-template.md)
4. Report PR URL

---

## Phase 5 — CI develop (wait)

```bash
gh pr checks <pr-number> --watch
```

Required green: `backend (ruff + pytest)`, `frontend (lint + build)` from `ci-develop.yml`.

On failure: push fixes, re-watch. Do not merge until all required checks pass.

---

## Phase 6 — Merge to develop

```bash
gh pr merge <pr-number> --squash --delete-branch
git checkout develop && git pull origin develop
```

Confirm `git status` clean. Run `git cleanup` if remote branch was deleted.

---

## Phase 7 — Wait for dev deployment

Fly deploy runs after CI (develop) succeeds on push. Poll until healthy:

```bash
# CI on develop push (post-merge)
gh run list --branch develop --workflow "CI (develop)" --limit 1
gh run watch <run-id>

# Fly deploy (triggered by CI success)
gh run list --branch develop --workflow "Fly Deploy (develop)" --limit 1
gh run watch <fly-run-id>

# Dev stack readiness (API + frontend)
until curl -sf https://api-dev.marrow-health.com/api/v1/health; do sleep 15; done
until curl -sf https://app-dev.marrow-health.com >/dev/null; do sleep 15; done
```

If health never recovers within ~15 min, surface blocker — do not proceed to smoke test.

---

## Phase 8 — Dev environment smoke test

Manual verification on **https://app-dev.marrow-health.com** (email + password login).

Checklist:

- [ ] Golden path from acceptance criteria works in dev UI
- [ ] At least one error/edge path fails gracefully
- [ ] No new 500s in dev backend logs during test (if accessible)
- [ ] Migration-sensitive changes: exercise against real Postgres dev, not SQLite-only local

Record evidence (screenshots/snapshots + short notes). If smoke FAIL: open hotfix branch → fix → repeat Phases 3–7.

---

## Phase 9 — PR develop → main

Only after Phase 8 PASS:

```bash
git checkout develop && git pull origin develop
gh pr create --base main --head develop --title "Release: <short summary>" --body "$(cat <<'EOF'
## Summary
- <bullets of what shipped since last main promotion>

## Dev verification
- [x] CI (develop) green on merge commit
- [x] Dev smoke on app-dev.marrow-health.com — <1-line result>

## Test plan
- [ ] CI (main) — awaiting checks
- [ ] Final human review before merge

EOF
)"
```

---

## Phase 10 — CI main (wait)

```bash
gh pr checks <pr-number> --watch
```

Required green from `ci-main.yml` (stricter frontend prod-shaped build).

On failure: fix on `develop`, re-promote. Do not ask for final review until green.

---

## Phase 11 — Final review (human)

When CI main is green:

1. Post summary: develop PR link, dev smoke results, main PR link, CI status
2. **Ask Leo for final review** — do NOT auto-merge to `main`
3. After approval: Leo merges (or explicit "merge it" instruction)

---

## Memory ritual

- Read sub-agent memory before every dispatch
- Write gotchas back after every sub-agent completes
- Persist durable user feedback to `~/.cursor/agent-memory/` when given

## Anti-patterns

- Plan without sub-agent map
- Orchestrator implementing multi-file work solo
- PR without filled-in test results
- Merging develop PR with red CI
- Skipping dev smoke before main PR
- Auto-merging to `main` without explicit approval
- `--no-verify`, force-push to `develop`/`main`
