# Repository coding agents

Eight technical roles work across all F0rge apps: `f0rge-backend`, `f0rge-frontend`,
`f0rge-data`, `f0rge-security`, `f0rge-delivery`, `f0rge-devops`,
`f0rge-workflows` and `f0rge-quality-testing`. These are repository coding roles;
they do not replace personal bots or rewrite user-global profiles or memory.

## Sources and generated adapters

`docs/adr/README.md` is the canonical decision index. `docs/agents/manifest.json`
holds role metadata and ordered routing rules. `docs/agents/protocol.md` supplies
the shared brief; `docs/agents/profiles/` holds the role bodies. Keep instruction
changes in those sources and regenerate the adapters.

Only Codex and Cursor adapters are generated:

- `.codex/agents/f0rge-*.toml`
- `.cursor/agents/f0rge-*.md`

The generator embeds the shared protocol and selected profile body. References
inside them are literal repository-root-relative paths so they retain their
meaning in either adapter. Edit the source, not an embedded generated copy.
The manifest is repository metadata, not a native tool permission configuration.
No model or provider is selected by these profiles.

Native formats are documented by [Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents)
and [Cursor](https://cursor.com/docs/subagents). The shared Markdown sources and
routing manifest are repository conventions; neither is a universal agent loader.

## Routing and handoffs

Run from the repository root:

```bash
node scripts/agents/agents.mjs route apps/marrow/backend/scripts/export_openapi.py
node scripts/agents/agents.mjs route libs/backend/testing/src/f0rge_testing/fixtures.py
node scripts/agents/agents.mjs route docs/adr/operations.md
```

The first matching ownership rule chooses one primary. Reviewer requirements
accumulate across matching rules; matching the primary does not cancel review.
When a reviewer has the same role ID as the primary, use a separate reviewing
instance. A self-check is useful evidence but is not independent review.
Unknown paths require classification rather than a default owner.
Path routing supplies a minimum review baseline. Identity, permission, isolation,
grant, sensitive-data or contract changes also require the relevant reviewers
based on behavior, even when a neutral filename matches no special path rule.

The orchestrator uses that result to assign each chunk, its dependencies and
required evidence. It also arranges cross-domain and independent review. Workers
must not assume that their harness can spawn another worker. If native delegation
is unavailable, report the handoff/review requirement; do not claim it happened.
Role selection and plaintext instructions do not grant access or enforce a sandbox.

## Review references

Every reviewer reads `.cursor/review-context/_shared/*.md`, then the relevant
existing area playbook. These are review references, not another ownership map.

| Review area | Existing playbook |
| --- | --- |
| Backend; legacy Python persistence/API changes | `.cursor/review-context/fastapi-backend-playbook.md` |
| Frontend and client contracts | `.cursor/review-context/frontend-dev-playbook.md` |
| Delivery and DevOps | `.cursor/review-context/devops-playbook.md` |
| Quality/testing evidence | `.cursor/review-context/qa-engineer-playbook.md` |

Data, security and workflows reviewers select the affected-area playbooks from
their diff, alongside their own required ADR readings. There are no invented
dedicated playbook files for these roles. Historical playbook names and memory
citations are preserved as provenance; they are not calls to the old global roles
or a requirement to possess another user's memory directory. Apply each legacy
checklist within its documented app/framework scope.

## Change and verify

After an approved instruction change:

```bash
npm run agents:generate
npm run agents:check
npm run agents:test
```

The direct generation and consistency commands are
`node scripts/agents/agents.mjs generate` and
`node scripts/agents/agents.mjs check`. Review the canonical and generated diffs
together. Include representative routing cases for contracts, database models,
shared harnesses, runtime configuration and unknown paths; retain accumulated
reviewers when a specific rule overrides a broad primary.

Static checks establish only what the checker actually inspects: source/metadata
consistency, valid references, generated output and routing cases. They do not
prove that a native harness discovered or invoked a profile, that its worker
followed every instruction, or that the accepted ADRs are implemented.

For each installed supported harness, use its supported discovery/invocation
mechanism in a fresh repository session. Dispatch a read-only task to a generated
role, confirm which profile was selected, and record the invocation, observed
result and any unavailable capability. Keep this native smoke evidence separate
from generator tests. An unavailable Cursor or Codex smoke is reported as not run,
not replaced by a successful file scan.

Instruction-only changes need these checks and independent review. App behavior
changes still need their applicable builds, tests and live-server walkthroughs.
P-001 through P-064 remain accepted and C-001/C-002 conditional. The profiles do
not install missing ADR enforcement or implement the release-tag and immutable
artifact mechanisms described by P-045/P-046. The all-ADR PR checklist and Leo's
production-release approval remain required; no agent or generated file supplies
that consent.
