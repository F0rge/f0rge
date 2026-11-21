# Data

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-016

- **Policy status:** Accepted
- **Temporary ID:** P-016
- **Category:** Data
- **Decision:** PostgreSQL is the default database for new apps.
- **Proposed enforcement (not installed):** App template, service configuration schema and integration harness select PostgreSQL; test fixtures use its actual engine.
- **Gate and limit:** Static + integration: configured engine and database test report. Existing SQLite/other stores are migration inventory items, not silently changed.
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
- **Static evidence at `f155a2ba` (not normative, not a live check):** Docs only. No checker compares Railway project IDs.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-020

- **Policy status:** Accepted (amended by Leo’s 15 and 20 November 2026 requests)
- **Temporary ID:** P-020
- **Category:** Data
- **Decision:** Migrations run unattended as the Host's pre-release step for every App that has them: once per Release, never at each instance's startup. There is no per-release approval and no backup check before them. Keep each migration compatible with the previous commit's code, because the automatic rollback puts the old code back and never downgrades the schema. A destructive change (drop, rename, data removal) is called out in the PR with its recovery plan; the reviewer decides.
- **Amendment (15 November 2026):** Leo requested automatic migrations for Firstout's continuous deployment.
- **Amendment (20 November 2026):** Leo requested the same for every App, with no approval and no backup preflight. This replaces "other apps retain their explicit release approval".
- **Enforcement:** A service's `preDeployCommand` in its Project's deploy block is sent to Railway with each Release, and Railway runs it before the new code starts. A rollback does not run it. Firstout, Marrow and DasKasas commerce have one today. No Pi App has migrations today, and the release program refuses a `preDeployCommand` on a Pi service.
- **Gate and limit:** The reviewer judges migration safety; nothing in the pipeline classifies a migration. A migration that is not backward compatible can make the automatic rollback fail. No backup is checked or restored by the pipeline.
- **Approved exception:** None.
