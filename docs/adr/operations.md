# Operations

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-051

- **Policy status:** Accepted
- **Temporary ID:** P-051
- **Category:** Operations
- **Decision:** Health checks and operational visibility are mandatory on Pi and Railway. Firstout continuous deployment automatically verifies the exact backend/frontend image digests, running replicas, database-backed readiness and migration receipt, and served frontend assets before declaring success. Release verification failures trigger application recovery and pause subsequent releases.
- **Enforcement:** Firstout's controller checks fixed provider targets, settles each rollout, binds backend readiness to the candidate source/schema/policy receipt and verifies frontend JavaScript/CSS against tested hashes. A bounded post-deploy observation window repeats these checks. Other apps retain their existing release holds; this is not a claim of a platform-wide monitor.
- **Gate and limit:** Integration + runtime: health evidence is tied to the actual serving version. Checks use read-only endpoints and static assets, with no real charges, emails or customer writes. The controller's current six observations at ten-second intervals are implementation bounds, not approved platform SLOs. Full authenticated Clerk business journeys and continuous monitoring beyond that release window remain separate coverage.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Railway healthcheck configuration and a post-deploy HTTP smoke for components with health URLs. The smoke does not compare a deployed digest.
- **Implementation:** Firstout controller, workflow and boundary tests are implemented in `.github/deploy/firstout_cd.py` and `.github/workflows/cd-firstout.yml`; production credentials, baseline bootstrap and live activation are not performed by this PR. Other-app operational coverage remains partial.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-052

- **Policy status:** Accepted
- **Temporary ID:** P-052
- **Category:** Operations
- **Decision:** Both hosts require useful logs and resource limits.
- **Proposed enforcement (not installed):** Structured log adapter/redaction tests; deployment policy checks CPU/memory/concurrency limits and log retention/access configuration; exercise overload/failure behavior.
- **Gate and limit:** Config + runtime: limits and operational log evidence. Numeric values require workload assessment, not fabricated defaults.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Restart policy fields in some railway.toml files. No log redaction test and no limit schema.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-053

- **Policy status:** Accepted
- **Temporary ID:** P-053
- **Category:** Operations
- **Decision:** Use managed secrets; keep credentials and sensitive data out of source and exposed logs.
- **Proposed enforcement (not installed):** Secret references in deployment configuration, least-privilege distribution, secret scanning and redaction fixtures; review access/rotation and prevent logging raw request payloads/tokens.
- **Gate and limit:** Static + runtime + review: scan, secret-reference and log tests. Masking is defense in depth, not permission to log secrets.
- **Static evidence at `f155a2ba` (not normative, not a live check):** gitignore, audit of known vulnerable packages, and workflow secret references for Coolify and smoke. No secret scanner gate and no log-redaction fixture.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-054

- **Policy status:** Accepted
- **Temporary ID:** P-054
- **Category:** Operations
- **Decision:** Backups, tested restoration and recovery procedures are required on both hosts. Firstout may automatically recover an application release by restoring its captured previous immutable backend/frontend images in reverse deployment order, verifying recovery and pausing further releases. Application recovery never automatically downgrades PostgreSQL or restores a database snapshot; new business transactions must be preserved.
- **Enforcement:** Firstout preflight reads a recent, unexpired provider backup record belonging to its fixed PostgreSQL volume before any release mutation. The current 24-hour age bound is an implementation limit, not a repo-wide recovery target. Compatible schema changes and a tested previous backend image are required so old binaries can operate on the expanded database. Each mutation is journaled durably before submission; an ambiguous provider outcome is reconciled before another mutation. Recovery leaves a durable open incident and blocks later releases until an authorized operator reconciles it.
- **Gate and limit:** Boundary tests cover release failure, response loss, rollback, failed recovery and durable pause. Provider backup identity/age checks do not prove a restore drill or transaction-consistent recovery. Database restoration, destructive schema recovery and lost-data decisions require a separately approved incident plan. Restore drills, retention/cadence and recovery objectives remain explicit activation prerequisites; no backup is automatically restored as part of CD.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Two shell scripts. They are not invoked by CI. No restore test.
- **Implementation:** Firstout automatic image recovery and durable incident pause are implemented and tested at external boundaries. Live provider rehearsal, backup restoration evidence and activation are not established by this code change; other-app backup/recovery gaps remain.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

