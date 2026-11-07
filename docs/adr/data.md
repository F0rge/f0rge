# Data

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-016

- **Policy status:** Accepted
- **Temporary ID:** P-016
- **Category:** Data
- **Decision:** PostgreSQL is the default database for new apps.
- **Proposed enforcement (not installed):** App template, service configuration schema and integration harness select PostgreSQL; test fixtures use its actual engine.
- **Gate and limit:** Static + integration: configured engine and database test report. Existing Turso/other stores are migration inventory items, not silently changed.
- **Static evidence at `f155a2ba` (not normative, not a live check):** No template check that a new app selects PostgreSQL. Marrow and Firstout tests can start Postgres via testcontainers.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-017

- **Policy status:** Accepted
- **Temporary ID:** P-017
- **Category:** Data
- **Decision:** Each app owns its data. Other apps and Airflow use approved APIs, never direct cross-app database reads/writes.
- **Proposed enforcement (not installed):** Restricted DB grants and network/credential distribution; integration tests attempt forbidden cross-app connections/queries. Import/DSN checks are defense in depth; approved API contracts define allowed access.
- **Gate and limit:** Runtime + integration + review: grant audit and negative access tests. Lint cannot establish database isolation; no shared superuser credential.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Review comments and separate compose files. No negative cross-app connection test was identified as a platform gate.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-018

- **Policy status:** Accepted
- **Temporary ID:** P-018
- **Category:** Data
- **Decision:** On Pi, one PostgreSQL cluster with separate app databases and restricted app logins.
- **Proposed enforcement (not installed):** Provisioning-policy checks validate distinct DB/role mappings and grants; disposable-cluster tests prove app A cannot connect to/read app B.
- **Gate and limit:** Infra + integration: DB ownership/grants evidence. Shared cluster still shares resource/failure domain; no claim of hard host isolation.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-019

- **Policy status:** Accepted
- **Temporary ID:** P-019
- **Category:** Data
- **Decision:** On Railway, each app keeps its own project and PostgreSQL service; no giant shared F0rge app project.
- **Proposed enforcement (not installed):** Proposed deployment inventory validates app-to-project/DB mapping; approved infrastructure assessment checks project references and accidental shared credentials.
- **Gate and limit:** Infra + human: project/resource mapping. No account inspection performed, and sharing Airflow does not override separate app projects.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Docs and railway.toml comments. The deploy manifest does not include storefront or commerce. No checker compares Railway project IDs.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-020

- **Policy status:** Accepted
- **Temporary ID:** P-020
- **Category:** Data
- **Decision:** Tested migrations run as a controlled step in an approved release, not independently at each instance startup. Preserve compatibility; destructive changes need explicit approval and recovery.
- **Proposed enforcement (not installed):** Migration job with mutual exclusion and recorded completion; upgrade tests on PostgreSQL, old/new compatibility tests where applicable, startup test asserting no automatic migration. Classify destructive operations for review.
- **Gate and limit:** Test + release + human: migration logs, compatibility evidence and destructive-change approval/recovery plan. Do not promise every migration can be reversed with down SQL.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Some Alembic upgrade tests exist under Marrow and Firstout tests. CI e2e applies alembic upgrade head to its ephemeral database. No check fails when a container migrates on startup. No destructive-change classifier.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

