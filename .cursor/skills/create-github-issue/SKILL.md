---
name: create-github-issue
description: Draft and create agent-ready GitHub issues from a user description. Assesses whether work should be one issue or a parent with sub-issues, surfaces unclear product/technical decisions, shows a plain-language recommendation, then creates issues via gh CLI (or REST API fallback). Use when the user says create issue, write a github issue, /create-github-issue, file an issue, or describes work to be tracked for an agent to implement.
disable-model-invocation: true
---

# Create GitHub Issue (agent-ready)

Turn a rough idea into GitHub issue(s) that an agent can pick up with no prior chat context. **Do not create issues until the user approves the draft.**

## Principles (from research)

Issues for coding agents work best when they are:

- **One focused job** per issue — not a kitchen-sink epic in a single body
- **Self-contained prompts** — problem, goal, files, boundaries, testable acceptance criteria
- **Explicit about what not to do** — agents infer badly from omission
- **Small enough to verify** — if acceptance criteria need a novel, split it

Sources: [GitHub Copilot coding agent](https://docs.github.com/en/copilot/tutorials/cloud-agent/get-the-best-results), [Osmani — good spec for AI agents](https://addyosmani.com/blog/good-spec/), [GitHub sub-issues CLI](https://github.blog/changelog/2026-06-10-manage-sub-issues-types-and-dependencies-from-github-cli/).

---

## Phase 0 — Bootstrap

1. Confirm target repo: current workspace git remote, or ask (`owner/repo`).
2. Read repo agent context if present: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`.
3. If the repo defines an issue structure (e.g. `AGENTS.md` § "Writing issues for sub-agents"), **use that structure** instead of the default template in [references/issue-body-template.md](references/issue-body-template.md).
4. `gh auth status` — stop if not authenticated.

---

## Phase 1 — Understand the request

Extract from the user's description:

| Field | Question |
| --- | --- |
| Problem | What hurts today? (constraint, not solution) |
| Goal | What changes when this is done? |
| User-visible outcome | What can someone observe or click? |
| Touch areas | Backend, frontend, data, infra, ML, docs? |
| Risk | Prod/security/destructive/migration? |

If the description is too thin to draft acceptance criteria, ask 1–3 targeted questions before proceeding.

---

## Phase 2 — Scope assessment (single vs split)

Evaluate whether this should be **one issue** or a **parent epic + sub-issues**.

### Split into parent + sub-issues when any of these apply

| Signal | Plain English |
| --- | --- |
| Multiple independent deliverables | Several things could ship in separate PRs |
| Multiple layers | Backend + frontend + infra that don't have to land atomically |
| > ~5 specialist owners | Too many parallel workstreams for one agent session |
| > ~5 person-days estimated | Too large for one focused implementation pass |
| Phased delivery | Phase 2 depends on phase 1 but they are separable |
| Mixed risk classes | e.g. schema migration + UI polish in one ask |

### Keep as one issue when

| Signal | Plain English |
| --- | --- |
| Single cohesive change | One PR, one verification story |
| Tight coupling | Pieces only make sense together |
| Small scope | Roughly one layer, few files, clear owner |
| Bug fix or narrow enhancement | Obvious start/end |

### When uncertain

Use `AskQuestion` (or ask conversationally):

- **"One issue"** — everything ships together
- **"Parent + sub-issues"** — epic tracks the goal; children are agent-sized chunks
- **"Not sure — show me both"** — draft both structures for comparison

**Always present a recommendation** with a short plain-English explanation before creating anything.

Example:

> **Recommendation: parent + 3 sub-issues**
>
> You asked for auth, a new API, and a settings page. Those are three layers that can merge independently and need different specialists. One mega-issue would confuse an agent about where to stop. A parent holds the overall goal; sub-issues are sized for one agent run each.

---

## Phase 3 — Surface unclear decisions

Before drafting, scan for **product** and **technical** ambiguity the user did not resolve.

### Product decisions (examples)

- Which user roles / personas?
- Default behavior when data is missing?
- UX: modal vs page, opt-in vs opt-out?
- What is MVP vs nice-to-have?

### Technical decisions (examples)

- New table vs extend existing schema?
- Sync vs async, cache or not?
- Which API style / library / pattern?
- Feature flag or ship fully on?

**Rules:**

- If the codebase or `AGENTS.md` already decides → **don't ask**; state the assumption in the draft.
- If genuinely open → list under **Open decisions** in the preview and use `AskQuestion` with a **recommended option first**.
- Explain each option in simple terms (one line each).
- Unresolved decisions block issue creation unless the user explicitly says "file it with TBD — agent should ask during planning."

---

## Phase 4 — Draft preview (mandatory gate)

Show the user a preview **before** `gh issue create`. Include:

1. **Recommendation** — one issue vs parent+children (plain English why)
2. **Titles** — parent (if any) + each sub-issue
3. **Full bodies** — use templates from [references/issue-body-template.md](references/issue-body-template.md)
4. **Dependency order** — which sub-issue blocks which (if split)
5. **Labels / assignees** — if inferable or user-specified
6. **Open decisions** — anything still TBD

Ask: **"Create these issues as drafted?"** Only proceed on explicit approval.

---

## Phase 5 — Create on GitHub

Use `gh` from the repo root (or `-R owner/repo`). Commands: [references/gh-commands.md](references/gh-commands.md).

### Order of operations (split work)

1. Create **parent** issue → capture number
2. Create each **sub-issue** linked to parent
3. Set **blocked-by** edges between sub-issues if needed
4. Edit parent body to list sub-issue links (if not auto-listed)
5. Return all URLs to the user

### Order of operations (single issue)

1. Write body to a temp file
2. `gh issue create --title "..." --body-file ...`
3. Return URL

### gh version note

Sub-issue flags (`--parent`, `--add-sub-issue`, `--blocked-by`) need **gh ≥ 2.94**. If older, use REST fallback in [references/gh-commands.md](references/gh-commands.md) or tell the user to upgrade: `brew upgrade gh`.

---

## Phase 6 — Handoff

After creation, tell the user:

- Links to parent and sub-issues
- Suggested next step: `/issue-implement N`, `ship-feature`, or assign to an agent
- Any decisions left TBD that planning must resolve first

Do **not** start implementation unless the user asks.

---

## Anti-patterns

| Bad | Good |
| --- | --- |
| Vague AC: "user can log in" | `POST /auth/login` with valid creds → 200 + `ht_session` cookie |
| Implicit scope | Explicit **Out of scope** section |
| One 2,000-line epic issue | Parent + focused sub-issues |
| Skipping the preview gate | Always show draft + recommendation first |
| Asking preferences already in `AGENTS.md` | Cite the file; don't re-ask |
| Creating issues with unresolved blockers | Mark TBD or get user sign-off |

---

## Additional resources

- Body templates: [references/issue-body-template.md](references/issue-body-template.md)
- `gh` / API commands: [references/gh-commands.md](references/gh-commands.md)
