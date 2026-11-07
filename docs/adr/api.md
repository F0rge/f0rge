# API

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-021

- **Policy status:** Accepted
- **Temporary ID:** P-021
- **Category:** API
- **Decision:** Rust endpoint/request/response definitions are authoritative; generate the API contract and typed React clients, with compatibility checked in CI.
- **Proposed enforcement (not installed):** Regenerate contract/client and fail on diff; validate endpoint coverage; proposed OpenAPI breaking-change checker if OpenAPI is selected, plus old-client/new-server behavior tests.
- **Gate and limit:** Static + contract tests: generated diff, compatibility report. Generator not yet selected; schema diff cannot prove behavioral compatibility.
- **Static evidence at `f155a2ba` (not normative, not a live check):** marrow-frontend codegen:check when that project is affected. No oasdiff or behavioral compatibility suite.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-022

- **Policy status:** Accepted
- **Temporary ID:** P-022
- **Category:** API
- **Decision:** Shared API error format and shared frontend handling for field errors, permission failures and edit conflicts; no internal debug-detail leaks.
- **Proposed enforcement (not installed):** Common Rust error mapping and React error adapter; schema snapshots and negative tests for validation/403/409; assert sanitized messages and trace identifiers.
- **Gate and limit:** Test: error-envelope and UI state tests. Review logs/telemetry separately; schema shape alone does not prevent sensitive error text.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Handler unit coverage was not measured. One frontend test file exists. No platform negative tests for sanitized 403 and 409 bodies.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-033

- **Policy status:** Accepted
- **Temporary ID:** P-033
- **Category:** API
- **Decision:** Frontend validation helps the user; Rust validates authoritatively. Keep both coherent without assuming business/permission rules can all be generated.
- **Proposed enforcement (not installed):** Contract-derived constraints where representable; golden valid/invalid payload fixtures exercised on client and server; direct invalid-request tests bypass the browser.
- **Gate and limit:** Contract + integration: validation parity and backend rejection evidence. Authorization, uniqueness and DB-dependent checks stay backend-owned.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Framework validation plus scattered tests. No golden valid/invalid payload suite shared with the client. Direct invalid-request tests exist in places but were not counted as a gate.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

