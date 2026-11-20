# Product

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-008

- **Policy status:** Accepted
- **Temporary ID:** P-008
- **Category:** Product
- **Decision:** Before an app or substantial feature: agree a short brief, testable outcomes and clickable mockup with Leo.
- **Proposed enforcement (not installed):** Proposed feature brief template links user/problem/scope, acceptance tests, mockup and approval; PR references the brief and explains small-change exemptions.
- **Gate and limit:** Human + PR schema: verify links/approval exist; owner judges substantial scope and mockup quality.
- **Static evidence at `f155a2ba` (not normative, not a live check):** No PR schema checks for a brief or mockup link.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-009

- **Policy status:** Accepted
- **Temporary ID:** P-009
- **Category:** Product
- **Decision:** Design and test loading, empty, error, denied, success and edit-conflict states.
- **Proposed enforcement (not installed):** State matrix in feature brief; deterministic fixtures drive Storybook/browser scenarios and critical end-to-end journeys.
- **Gate and limit:** Test + review: state coverage map, screenshots/traces and acceptance evidence. Existence of a story alone is insufficient.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Vitest files and Storybook stories for some primitives. A Playwright job ran Marrow e2e only when the detect job selected it.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-010

- **Policy status:** Accepted
- **Temporary ID:** P-010
- **Category:** Product
- **Decision:** Implement the Buycycle ADR migration first; perform the holiday-explorer platform pilot later. Both stay on approved platform destinations; no standalone off-platform deployment.
- **Decision update (15 November 2026):** Leo explicitly requested the complete Buycycle migration before the later pilot, in one PR with issue-sized commits. The holiday-explorer pilot is not a prerequisite for this authorized Buycycle migration. This sequencing change grants no merge, production release or destructive data-migration approval.
- **Proposed enforcement (not installed):** Pilot checklist exercises shared UI, auth, API, local startup, CI and approved release controls; release routing accepts only approved platform destinations.
- **Gate and limit:** Pilot review + release: end-to-end evidence for each authorized migration and the later pilot. No production deployment is authorized by this record.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for a holiday-explorer pilot checklist.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

