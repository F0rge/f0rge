# Health Tracker — Agent Instructions

**Extends `~/.cursor/rules/leo-system-wide.mdc`** — global preferences, stack defaults, git workflow, boundaries, and sub-agent delegation live there. This file is project-specific only.

## Project rules

Scoped rules in `.cursor/rules/` (auto-applied by glob):

| Rule | Scope |
|------|-------|
| `orchestration.mdc` | Always — planning must delegate to sub-agents |
| `backend.mdc` | `backend/**/*.py`, migrations |
| `frontend.mdc` | `frontend/**/*.tsx`, `frontend/**/*.ts` |
| `infra.mdc` | Docker, compose, CI, deploy |
| `qa-gate.mdc` | tests, workflows |
| `data-pipelines.mdc` | `backend/scripts/**`, `backend/data/**` |

See also `CLAUDE.md` for env URLs, key paths, and issue-writing template.

## Sub-agents

Delegate per `~/.cursor/rules/leo-system-wide.mdc` and `.cursor/rules/orchestration.mdc`. Every plan names a sub-agent per work chunk before implementation. Brief each sub-agent to read `~/.cursor/agent-memory/<agent-name>/MEMORY.md` before starting and write back gotchas when done.

## Shipping features

End-to-end workflow (prompt or GitHub issue → develop → dev smoke → main PR): `.cursor/skills/ship-feature/SKILL.md`.

## PR review context

Bugbot/PR review playbooks live in `.claude/review-context/`. A synced copy is at `.cursor/review-context/` — run `./scripts/sync-review-context.sh` after editing the source.

## Agent memory

**Canonical:** `~/.cursor/agent-memory/<agent>/` (global, cross-project).

The copy at `.claude/agent-memory/` (35 files) is legacy from the Claude Code migration. No CI workflow references it. Safe to delete once you've confirmed nothing else reads it — global memory already contains the merged health-tracker gotchas.
