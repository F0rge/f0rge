# Security

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-035

- **Policy status:** Accepted
- **Temporary ID:** P-035
- **Category:** Security
- **Decision:** Two auth modes: private approved-person access and customer accounts.
- **Proposed enforcement (not installed):** Schema-checked app auth-mode declaration; shared adapter interface and integration fixtures test allowed/denied/expired sessions for the chosen mode.
- **Gate and limit:** Config + test + review: auth-mode matrix. Do not elevate Clerk or a particular Access product into a repo-wide vendor mandate without confirmed selection.
- **Static evidence at `f155a2ba` (not normative, not a live check):** App tests assert cookie names. No inventory schema validates the mode. A Firstout test rejects the string ht_session in that app.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-036

- **Policy status:** Accepted
- **Temporary ID:** P-036
- **Category:** Security
- **Decision:** Use shared verified identity adapters; backend identity must be trustworthy.
- **Proposed enforcement (not installed):** Central token/session verification adapter; negative tests reject forged/expired/wrong-audience identity and spoofed gateway headers; restrict trusted ingress.
- **Gate and limit:** Security integration: identity-verification tests and ingress trust configuration. Frontend identity strings are not proof.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Marrow bearer tests exist, including a test file that sets a non-JWT cookie. No platform suite rejects forged audience or spoofed gateway headers for every app.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-037

- **Policy status:** Accepted
- **Temporary ID:** P-037
- **Category:** Security
- **Decision:** Combine RBAC and ABAC as needed through shared permission mechanisms; backend checks are authoritative and tenant-scoped.
- **Proposed enforcement (not installed):** Shared permission interface and deny-default test matrix for read/write/list/export/jobs; use roles plus resource/org/ownership attributes; test stale claims and denied actions.
- **Gate and limit:** Security tests + review: permission matrix and query-scope tests. Library selected after assessment; client-only hiding is not enforcement.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Firstout and Marrow tests cover parts of their own rules. No deny-default matrix runs for read, write, list, export, and jobs across apps.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-038

- **Policy status:** Accepted
- **Temporary ID:** P-038
- **Category:** Security
- **Decision:** Keep personal apps simple; enforce organization data isolation when agreed scope includes multiple customer organizations.
- **Proposed enforcement (not installed):** App scope declaration; multi-org apps require negative cross-tenant API, list, export, worker and cache tests plus appropriate database safeguards.
- **Gate and limit:** Integration + human: tenant isolation evidence. RLS can help when configured, but is not asserted as universal for every app.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Marrow migration and RLS helper. Comments in Marrow tests say the normal suite connects as superuser and bypasses RLS, with separate tests for NOBYPASSRLS. No universal cross-tenant API gate.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-039

- **Policy status:** Accepted
- **Temporary ID:** P-039
- **Category:** Security
- **Decision:** Development agents may read real personal/customer data only when needed for the assigned task, read-only and with sensitive fields masked.
- **Proposed enforcement (not installed):** Task-scoped read views/API access with masking and expiry; no production write/deployment credentials in dev/CI; audit access and prohibit real-data fixtures in git.
- **Gate and limit:** Runtime access + review: scoped access approval/log and masking tests. A read-only label in agent instructions is insufficient.
- **Static evidence at `f155a2ba` (not normative, not a live check):** gitignore for local databases and env files. No task-scoped masked view, expiry, or access audit.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

