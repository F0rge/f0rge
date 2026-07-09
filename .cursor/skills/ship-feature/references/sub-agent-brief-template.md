# Sub-agent brief template

Fill `{{...}}` variables. Send verbatim — do not skip memory or house-rules blocks.

---

## Memory bootstrap

1. **Read first**: `~/.cursor/agent-memory/{{agent-name}}/MEMORY.md`
2. **Write back**: decisions, gotchas, confirmed patterns

## House rules

1. **Think before coding.** State assumptions. Ask when unclear.
2. **Simplicity first.** No speculative abstractions or error handling for impossible cases.
3. **Surgical changes.** Every changed line traces to the assigned slice.
4. **Goal-driven.** Verifiable acceptance criteria per step.

## Repo + branch

`{{repo-path}}` on `{{feature-branch}}`. Plan section §{{plan-section-number}}.

## Hard rules

From `CLAUDE.md` + `.cursor/rules/*.mdc` for your scope.

## Scope

{{Paste plan slice: deliverables, paths, acceptance criteria.}}

## Acceptance

1. {{check 1}}
2. {{check 2}}

## Reporting back

Under 250 words: files touched, pass/fail per acceptance check, deviations, memory writes. Do not spawn sub-agents — report blockers to orchestrator.
