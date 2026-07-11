# PR body template (develop PR)

```markdown
Closes #{{issue-number}}.

## Summary

- {{what + why}}
- {{key design decision}}

## Sub-agent delegation

| Agent | Work |
| --- | --- |
| `fastapi-backend` | {{…}} |
| `frontend-dev` | {{…}} |
| `qa-engineer` | {{…}} |

## Test plan

- [x] `uv run ruff check .` + `ruff format --check` — clean
- [x] `uv run pytest` — {{N}}/{{N}} passing
- [x] `npm run lint` + `typecheck` + `build` — clean
- [x] Live-server E2E — {{paths driven}}
- [x] Simplify pass — {{delta}}

## Dev smoke (post-merge)

Orchestrator will verify on https://app-dev.marrow-health.com per ship-feature Phase 8.

## Known follow-ups

- {{deferred items only}}
```

Match recent PR tone. Real numbers, not "tests pass". Omit agents that were not dispatched.
