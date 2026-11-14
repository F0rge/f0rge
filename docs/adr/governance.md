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

- **Policy status:** Accepted
- **Temporary ID:** P-003
- **Category:** Governance
- **Decision:** Every PR to main includes an ALL-ADR compliance checklist, with statuses and justified exceptions.
- **Proposed enforcement (not installed):** Generate a complete appendix from the register for every main PR using [the PR process](../agents/pr-process.md), with distinct review and compliance status, existing gaps, evidence and reasons. An impacted-ADR summary may precede it, never replace it.
- **Gate and limit:** PR gate: adr-coverage verifies every current ADR appears and exceptions are valid. Checking a box is not proof; link real test/review evidence.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Ruleset main-pr-gate required_status_checks contexts ci and playwright smoke. No ADR appendix job.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-004

- **Policy status:** Accepted
- **Temporary ID:** P-004
- **Category:** Governance
- **Decision:** Deterministic automated architecture checks block merge and release where enforceable; exceptions need Leo.
- **Proposed enforcement (not installed):** Required architecture gate aggregates register, dependency, contract, test and policy results. Release rechecks approved commit/digest evidence. Protect checks and policy against tampering.
- **Gate and limit:** Merge + release: fail on missing, failed or unexpected skipped required checks. Semantic/human-only requirements stay explicit, not falsely automated.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Required contexts ci and playwright smoke on main. CI also runs check-nx-projects.sh, check-lib-boundary.sh, a libs/ import grep, npm audit, and marrow pip-audit when marrow-backend is affected.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-005

- **Policy status:** Accepted
- **Temporary ID:** P-005
- **Category:** Governance
- **Decision:** Independent agent review plus CI, not the implementing agent alone.
- **Proposed enforcement (not installed):** Separate reviewer receives diff, full ADR appendix and test artifacts; records findings and unresolved risks. CI independently computes mechanical results.
- **Gate and limit:** Review evidence + required tests. AI review is fallible/advisory evidence, not a security boundary or substitute for an authorized approval.
- **Static evidence at `f155a2ba` (not normative, not a live check):** CI aggregate job ci. No required human or independent-reviewer check. No CODEOWNERS file.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-006

- **Policy status:** Accepted
- **Temporary ID:** P-006
- **Category:** Governance
- **Decision:** Leo approves every production release.
- **Proposed enforcement (not installed):** Protected release approval bound to commit, artifact digest, target and migration plan; deploy credentials only in the approved release path. Disable alternate automatic production paths after assessment/approval.
- **Gate and limit:** Human + release: Leo approval record and deployed-digest receipt. GitHub environment reviewers or an equivalent controlled gate depend on available plan/permissions.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Deploy workflow guard requires a successful CI workflow_run on push or workflow_dispatch to main, or a direct workflow_dispatch. No Leo approval record and no environment required reviewers in the GET payload.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-007

- **Policy status:** Accepted (amended by Leo’s 14 November 2026 request)
- **Temporary ID:** P-007
- **Category:** Governance
- **Decision:** Codex is the supported repository coding harness. Maintain repository-aligned instructions through `AGENTS.md`, shared Markdown rules and review references under `docs/agents/`, procedure skills under `.agents/skills/`, and generated `.codex/agents/` profiles. Keep role routing in the manifest and independent review separate from implementation.
- **Rationale and trade-off:** Supporting multiple instruction adapters creates duplicate maintenance and hides useful rules behind editor-specific loading. Leo requested one Codex workflow and removal of the other adapter. Explicit scope pointers preserve the useful domain instructions without relying on editor rule attachment.
- **Enforcement:** `npm run agents:generate`, `npm run agents:check` and `npm run agents:test` maintain canonical-source/generated-profile consistency and representative routing cases. They do not enforce the whole ADR register or prove native discovery.
- **Proposed enforcement (not installed):** Repeatable native Codex discovery/invocation smoke and a deliberately violating task, with recorded instruction-load and negative-test evidence.
- **Gate and limit:** Static generation/routing checks plus independent review; native discovery and worker compliance require separate observed evidence. Plaintext profiles do not grant tools or permissions.
- **Static evidence at `f155a2ba` (historical, not normative, not a live check):** No instruction-discovery smoke test or deliberate-violation test was in CI.
- **Implementation:** Partial: repository role profiles and generation checks exist. This amendment consolidates the supported workflow; native discovery and deliberate-violation coverage remain separately reported verification.
- **Assessment label:** partial.
- **Approved exception:** None.
