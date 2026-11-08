# Operations

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-051

- **Policy status:** Accepted
- **Temporary ID:** P-051
- **Category:** Operations
- **Decision:** Health checks and operational visibility are mandatory on Pi and Railway.
- **Proposed enforcement (not installed):** App health/readiness contract and platform monitor configuration checks; dependency-failure fixtures test unhealthy signals and release health verification.
- **Gate and limit:** Integration + runtime: health evidence tied to deployed version. Passing HTTP liveness alone does not prove business workflow health.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Railway healthcheck configuration and a post-deploy HTTP smoke for components with health URLs. The smoke does not compare a deployed digest.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
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
- **Decision:** Backups, tested restoration and recovery procedures on both hosts.
- **Proposed enforcement (not installed):** Backup-policy checks plus isolated restore drills with recorded recovery evidence; include app DB/files and Airflow metadata/logs/versioned code/dependencies and recovery keys as applicable.
- **Gate and limit:** Runtime + human: successful restore record and runbook, not just a scheduled-backup checkbox. Recovery targets/cadence need assessment.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Two shell scripts. They are not invoked by CI. No restore test.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

