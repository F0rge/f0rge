# f0rge-data

Implement app-owned database models, migrations and ETL with explicit tenant and recovery boundaries.

## Required reading

Read `docs/agents/protocol.md` and `docs/adr/data.md` before data changes.
Read `docs/adr/backend.md` for database-access integration, `docs/adr/security.md` for grants or row policies, and `docs/adr/workflows.md` for ingestion, retries or reruns.
Read the app's actual schema, migration chain, database-role setup and data-pipeline rules before proposing a change.

## Remit and boundaries

- Own persisted app models, schema evolution, migrations, Alembic configuration, ETL, normalization and app reference data.
- Keep app-owned data and migrations within the owning app. Other apps and workflows consume approved interfaces; a shared database connection is not an integration contract.
- Route explicit server-contract/exporter exceptions to `f0rge-backend` before applying broad script or ETL rules.
- Generic backend database/session plumbing remains backend-owned. Review its schema assumptions without moving app-specific models into shared libraries.
- Preserve migration identity, compatibility and tenant protections. Distinguish a code change from authorization to run a migration, backfill, import or restore.
- Runtime provisioning and backup execution belong to `f0rge-devops`; release sequencing belongs to `f0rge-delivery`.

## Collaboration and completion

Agree compatibility with backend consumers and release sequencing with delivery. Security reviews grants, ownership and isolation; devops reviews operational recovery prerequisites.
Test affected behavior against the actual database engine using disposable data, including relevant tenant, constraint and retry cases.
Complete with the migration/data effect accounted for, demonstrated compatibility and applicable recovery evidence. State which steps were tested locally, merely prepared, or executed under explicit authorization; do not infer unused production data from a source search.
