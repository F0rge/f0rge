# Plan template

Use in Phase 1. Every section below is required.

---

# Plan — <Issue #N or prompt title>

## 1. Context

Why this change is being made. User-visible outcome. 2–4 sentences.

## 2. Research summary

### Codebase
- Pattern at `path:line` — reuse note
- Similar feature: `<name>` at `<files>`

### Web / external (or "skipped — internal only")

## 3. Sub-agent map (mandatory)

| Chunk | Owner | Deliverable | Depends on |
| --- | --- | --- | --- |
| … | `fastapi-backend` | … | — |
| … | `frontend-dev` | … | backend slice |
| … | `qa-engineer` | Gate report + e2e | all slices |

Every owner is a sub-agent from `~/.cursor/agents/`. Trivial single-file edits: one specialist only.

## 4. Detailed slices

One subsection per map row: files, acceptance criteria, non-obvious decisions.

## 5. Critical files

### New
- `path` — purpose

### Modified
- `path` — purpose

## 6. Open items

Decisions needing user sign-off before Phase 2.

## 7. Verification plan

1. Lint + tests + build commands
2. Local live-server E2E (if UI/API)
3. Dev smoke on `app-dev.marrow-health.com` after merge to develop
