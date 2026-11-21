# Governance

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-001

- **Policy status:** Accepted
- **Temporary ID:** P-001
- **Category:** Governance
- **Decision:** Repo-wide ADRs are authoritative. AGENTS.md points to them; no drifting policy copies.
- **Proposed enforcement (not installed):** Proposed docs/adr index + decision metadata; adr-register check validates IDs, status, scope, supersession and enforcement links. Generate/check pointer files, not duplicate prose.
- **Gate and limit:** Static + review: index/link report and generated-file diff. Human review still judges rationale; these paths are proposed.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None. Search of the tree found no docs/adr directory, no ADR index, and no adr-register checker.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-002

- **Policy status:** Accepted
- **Temporary ID:** P-002
- **Category:** Governance
- **Decision:** One default stack, exceptions approved by Leo. Apply new standards to new apps first; migrate existing apps gradually.
- **Proposed enforcement (not installed):** Schema-checked app inventory and template tests; compare new apps with approved stack. Versioned exception records name scope, owner, reason, expiry, tests and Leo approval.
- **Gate and limit:** Static + human: stack-policy report. Inventory legacy deviations before enforcement; no implicit grandfathering or forced rewrite.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Nx project.json tags and check-nx-projects.sh register projects. They do not compare a project to an approved stack or require a Leo exception record.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-003

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 requests)
- **Temporary ID:** P-003
- **Category:** Governance
- **Decision:** Every PR to main includes an ADR Check covering only the ADRs of the domains it touches: the ADR files of the owning role of each changed path (`node scripts/agents/agents.mjs adrs`), each with a compliance status and reason. The PR body follows the `pr` skill. The ADR Check is information for the reviewer, who decides (P-004).
- **Enforcement:** None in CI. The reviewer reads the ADR Check with the diff and the test evidence.
- **Approved exception:** None.

## P-004

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-004
- **Category:** Governance
- **Decision:** ADR compliance is not enforced by CI/CD. The reviewer decides, even where an ADR is broken. The pipeline contains no code whose only purpose is to prove an ADR was followed. Cheap guards that catch real breakage stay.
- **Amendment (20 November 2026):** Leo requested that CI/CD stop enforcing ADR compliance. This replaces "deterministic automated architecture checks block merge and release where enforceable". The ADR Check in PR descriptions (P-003) stays, as information for the reviewer.
- **Enforcement:** `merge-gate` is the single required check. It runs lint, format, typecheck, tests and builds (on `main`, skipped for trees that already passed it), the Artifact health check and the guards for real breakage: Nx project registration, the libs-to-apps boundary, OpenAPI drift, dependency audits and the agent-profile checks.
- **Approved exception:** None.

## P-005

- **Policy status:** Accepted
- **Temporary ID:** P-005
- **Category:** Governance
- **Decision:** Independent agent review and required CI accompany Leo's personal review of the code. Leo is the sole required code owner. Agent-prepared PRs default to GitHub's native automatic squash merge after his approval and all GitHub requirements pass; another merge confirmation is not required unless the task withholds merge authorization.
- **Amendment (15 November 2026):** Leo requested removal of Luis from required approvers and automatic squash merging after Leo's review. This replaces the earlier blanket prohibition on auto-merge. App-authored PRs let Leo review without being their author; agents never submit the required human approval through Leo's account.
- **Enforcement:** The App authors the PR; the existing authorized GitHub CLI identity requests native squash auto-merge with the expected current head checked when arming it. Effective protected-main rules must require Leo's code-owner review, dismiss stale approvals when reviewable code changes, require successful checks and resolved threads, and allow no bypass. Independent review receives the diff, the touched-domain ADR Check and test evidence; CI independently computes mechanical results. The publisher App remains separate and cannot push or merge contents.
- **Gate and limit:** The head check applies when auto-merge is armed, not an immutable lease on its eventual merge SHA. GitHub may retain approval for unchanged-diff rebases or empty commits; do not promise fresh review after every SHA change. Native GitHub requirements govern the queued merge. Activation requires the global sole-owner file on protected `main` and verified settings/rules; source policy and a working bot alone do not establish it. AI review never substitutes for Leo's personal review. Production authorization remains governed by P-006.
- **Static evidence at `f155a2ba` (not normative, not a live check):** CI aggregate job ci. No required human or independent-reviewer check. No CODEOWNERS file.
- **Implementation:** Publisher identity and human-review smoke are verified separately from the prepared ownership/default-merge changes; activation evidence belongs in the [publisher guide](../agents/github-publisher.md). This policy amendment does not arm any PR for merging.
- **Assessment label:** partial.
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-006

- **Policy status:** Accepted (amended by Leo’s 15 and 20 November 2026 requests)
- **Temporary ID:** P-006
- **Category:** Governance
- **Decision:** Every App is released automatically after a reviewed merge to `main` with CI passing. There is no per-release approval. Review and automatic squash merging follow P-005.
- **Amendment (15 November 2026):** Leo requested automatic deployment for Firstout.
- **Amendment (20 November 2026):** Leo requested the same for every App: migrations included (P-020), no per-release approval, no backup preflight, no release tags (P-045). This replaces the Firstout-only scope and the release holds on the other Apps.
- **Enforcement:** `ci.yml` calls `cd.yml` as its last job on pushes to `main`, after the `merge-gate` check. `cd.yml` runs one job per affected App in the GitHub environment named after the App, which holds that App's Host token. Releases of one App run one at a time, in merge order. A running Release is never cancelled; a newer one replaces a Release still waiting in the queue. A failed Release puts each service back on the image it ran before and fails the run. A manual run releases a commit that CI already built on `main`: `gh workflow run cd.yml -f app=<app> -f commit=<sha>`.
- **Gate and limit:** Leo's review (P-005) and the `merge-gate` check are the gate. An App that has not been switched at its Host fails closed. Provider operations outside this pipeline, and moving an App to another Host (P-047), still need their own task authorization. Nothing checks a whole App before production.
- **Approved exception:** None.

## P-007

- **Policy status:** Accepted (amended by Leo’s 14 and 20 November 2026 requests)
- **Temporary ID:** P-007
- **Category:** Governance
- **Decision:** Codex and Claude Code are the supported repository coding harnesses, with an identical setup generated from one source. Maintain repository-aligned instructions through `AGENTS.md` (read natively by both; no `CLAUDE.md`), shared Markdown rules and review references under `docs/agents/`, procedure skills under `.agents/skills/` (linked into `.claude/skills/`), and generated `.codex/agents/` and `.claude/agents/` profiles. Keep role routing in the manifest and independent review separate from implementation.
- **Rationale and trade-off:** Supporting multiple instruction adapters creates duplicate maintenance and hides useful rules behind editor-specific loading. Leo requested one Codex workflow and removal of the other adapter (14 November), then Claude Code support with an identical setup (20 November). Claude Code adds no second instruction source: both harnesses' profiles and skill links are generated from the same files, and the checks fail on any divergence. Explicit scope pointers preserve the useful domain instructions without relying on editor rule attachment.
- **Enforcement:** `npm run agents:generate`, `npm run agents:check` and `npm run agents:test` maintain canonical-source/generated-profile consistency, Codex/Claude Code parity (byte-identical role instructions; every shared skill linked, none harness-only) and representative routing cases. They do not enforce the whole ADR register or prove native discovery.
- **Proposed enforcement (not installed):** Repeatable native Codex and Claude Code discovery/invocation smoke and a deliberately violating task, with recorded instruction-load and negative-test evidence.
- **Gate and limit:** Static generation/routing checks plus independent review; native discovery and worker compliance require separate observed evidence. Plaintext profiles do not grant tools or permissions.
- **Static evidence at `f155a2ba` (historical, not normative, not a live check):** No instruction-discovery smoke test or deliberate-violation test was in CI.
- **Implementation:** Partial: repository role profiles and generation checks exist. This amendment consolidates the supported workflow; native discovery and deliberate-violation coverage remain separately reported verification.
- **Assessment label:** partial.
- **Approved exception:** None.
