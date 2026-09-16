# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **multi-context**. Read `CONTEXT-MAP.md` at the root when it exists; then only the `CONTEXT.md` files that match the work.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root: index of contexts. Read each relevant `CONTEXT.md`.
- **`docs/adr/`**: system-wide ADRs that touch the area you're about to work in.
- Per-app ADRs next to that app's `CONTEXT.md` when they exist.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

```
/
├── CONTEXT-MAP.md
├── docs/adr/                              ← system-wide decisions
├── apps/marrow/CONTEXT.md
├── apps/vellano/CONTEXT.md
└── apps/dk/tag-printer/CONTEXT.md
```

Shared libraries (`libs/backend/*`, `libs/ui`) inherit the consuming app's context unless `CONTEXT-MAP.md` adds a `libs/` entry later.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
