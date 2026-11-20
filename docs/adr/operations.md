# Operations

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-051

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-051
- **Category:** Operations
- **Decision:** Health checks and operational visibility are mandatory on Pi and Railway. Every Artifact is health-checked in CI before it is pushed, and every Release waits until the Host reports the new services healthy.
- **Amendment (20 November 2026):** Leo requested one pipeline for every App (P-006). This replaces the Firstout-only controller with its digest, receipt and asset-hash checks.
- **Enforcement:** A service's `healthcheckPath` in its Project's deploy block is used by the CI image check and sent to Railway with each Release. On the Pi, Coolify's own Healthcheck stays off: each Pi image carries a Docker `HEALTHCHECK`, and a service counts as healthy only when Coolify reports `running:healthy` (or `running:unknown`) throughout a settle window (90 s by default). `.github/deploy/deploy.mjs` polls the Host until each service succeeds or fails, within a timeout per service (900 s by default); a failed Release puts each service back on the image it ran before (P-054).
- **Gate and limit:** A service without a health path is judged by the Host's deployment status alone. Nothing checks a whole App before production, and there is no platform-wide monitor.
- **Approved exception:** None.

## P-052

- **Policy status:** Accepted
- **Temporary ID:** P-052
- **Category:** Operations
- **Decision:** Both hosts require useful logs and resource limits.
- **Proposed enforcement (not installed):** Structured log adapter/redaction tests; deployment policy checks CPU/memory/concurrency limits and log retention/access configuration; exercise overload/failure behavior.
- **Gate and limit:** Config + runtime: limits and operational log evidence. Numeric values require workload assessment, not fabricated defaults.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Restart policy fields in some provider config files. No log redaction test and no limit schema.
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

- **Policy status:** Accepted (amended by Leo’s 20 November 2026 request)
- **Temporary ID:** P-054
- **Category:** Operations
- **Decision:** Backups, tested restoration and recovery procedures are required on both hosts. A failed Release of any App automatically puts each service it touched back on the image it ran before, and fails the run. That rollback never downgrades a database or restores a backup.
- **Amendment (20 November 2026):** Leo requested automatic rollback for every App and no backup preflight (P-006, P-020). This replaces Firstout's backup check, release journal and release pause.
- **Enforcement:** Before changing a service, `.github/deploy/deploy.mjs` records the image the Host has it configured to run. On failure it puts each touched service back on that image, in reverse order and without its `preDeployCommand`, then exits non-zero. A service with no previous image (a first Release, or one still built from the repository) is left as it is. The App is released again on the next run on `main`.
- **Gate and limit:** No backup is checked before a Release or its migrations. A migration that is not backward compatible can make the rollback fail. Database restoration is a separately authorized operation. Backup cadence, restore drills and recovery targets are not set or checked by the pipeline.
- **Approved exception:** None.
