# Issue body templates

Adapt section names to match repo `AGENTS.md` when present. Every issue must stand alone — an agent may never read the parent or sibling issues.

---

## Single issue (default)

```markdown
## Problem (Why)

[One paragraph: what hurts now. Constraint, not solution.]

## Goal

[One sentence: what changes when this is done.]

## Proposed approach

[High-level design — not line-by-line implementation. Name key patterns to reuse.]

## Files

### Existing (modify)
- `path/to/file` — [why / starting point]

### New
- `path/to/file` — [purpose]

## Out of scope

- Do not change [X]
- Do not add [Y]

## Boundaries

**Always (no ask):**
- [e.g. follow existing lint/test commands]

**Ask first:**
- [e.g. new dependencies, schema changes]

**Never:**
- [e.g. force-push, secrets in repo, `--no-verify`]

## Acceptance criteria

- [ ] [Concrete, objectively verifiable criterion]
- [ ] [Include how to verify — command, endpoint, UI path]
- [ ] [Live-server walkthrough if UI/API — not "tests pass" alone]

## Dependencies

- **Blocked by:** [issue # or none]
- **Blocks:** [issue # or none]
- **Required env / secrets:** [or none]

## Rollback

[Only for destructive or production-affecting work: trigger + revert steps. Otherwise: "N/A — additive change."]
```

---

## Parent (epic) issue

Parent issues coordinate; they are **not** a dumping ground for full implementation detail. Keep acceptance criteria at the **epic** level.

```markdown
## Problem (Why)

[Why this body of work exists.]

## Goal

[User-visible outcome when all sub-issues are done.]

## Sub-issues

| # | Title | Owner | Depends on |
| --- | --- | --- | --- |
| [#N](url) | [title] | [agent/layer] | — |
| [#N](url) | [title] | [agent/layer] | #N |

## Epic acceptance criteria

- [ ] All sub-issues closed
- [ ] [End-to-end outcome verifiable in dev/prod]
- [ ] [No regressions in golden path X]

## Decisions (resolved)

| Decision | Choice | Rationale |
| --- | --- | --- |
| [e.g. auth model] | [JWT cookie] | [matches existing stack] |

## Open decisions

- [ ] [TBD — must be resolved before sub-issue #N]

## Out of scope (whole epic)

- [What this project explicitly does not include]

## Notes for agents

- Implement **sub-issues**, not this parent directly.
- Read repo `AGENTS.md` / `CLAUDE.md` before starting any child.
```

After sub-issues exist, edit the parent table with real issue numbers and URLs.

---

## Sub-issue

Each sub-issue is a **full agent prompt** for one slice.

```markdown
## Parent

Epic: #PARENT — [parent title]

## Problem (Why)

[This slice's piece of the problem — understandable without reading parent.]

## Goal

[One sentence for this slice only.]

## Proposed approach

[Design for this slice. Reference parent decisions table if relevant.]

## Files

### Existing (modify)
- `path` — [purpose]

### New
- `path` — [purpose]

## Out of scope

- [What this slice must not touch — especially sibling slices]

## Boundaries

**Always:** …
**Ask first:** …
**Never:** …

## Acceptance criteria

- [ ] [Verifiable for this slice only]
- [ ] [Tests / commands to run]

## Dependencies

- **Blocked by:** [#N or none]
- **Blocks:** [#N or none]

## Rollback

[N/A or slice-specific revert]
```

---

## Title conventions

| Type | Pattern | Example |
| --- | --- | --- |
| Single | `[area] imperative outcome` | `feat(auth): add password reset flow` |
| Parent | `epic: outcome` | `epic: user notification preferences` |
| Sub-issue | `[area] slice outcome` | `backend: notifications preference API` |

Use repo commit/PR conventions when documented.
