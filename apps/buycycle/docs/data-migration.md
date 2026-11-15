# Buycycle data migration and recovery

This procedure prepares a migration; it does not authorize a production import,
writer cutover, provider change or release. The running Turso database remains
authoritative until the separately approved cutover fences its collector.

## Preservation contract

The five source tables are `listing`, `price_history`, `detail`, `runs` and
`country_map`. PostgreSQL stores each complete source row in app-local
`legacy_record`, with an allowlisted table name and an unambiguous JSON encoding
of the original primary-key tuple. No nullable column, historical observation,
unknown extra scalar column, ID, original money integer or text field is dropped
or coerced. Existing dangling history is preserved rather than silently removed
to satisfy a newly invented foreign key.

The importer validates duplicate keys, the exact five-table set, source schema,
all row values, per-table SHA-256 and the safety ledger before beginning writes.
Conflicting existing keys fail the entire transaction. It reconciles each stored
table against the source hash before committing. A previously imported exact
bundle returns an idempotent result and never overwrites newer collector data.
Explicit `--reconcile` compares the current database to the source; it will
correctly report divergence after later observations are collected.

`import_manifest` retains the original complete bundle, source schema, processing
version, exported timestamp, safety ledger and reconciliation report. Hashes prove
integrity and exact semantic row reconciliation, not source authenticity or
permission to import. Keep source copies and their custody/release records too.
No database, export, screenshot of personal state or feed key belongs in Git.

## Export the legacy database

1. Obtain the exact cutover release approval and fence every old writer. The old
   supported collector uses the canonical `<db>-tracker.lock`; an unknown writer
   ignoring that lock must be stopped independently.
2. Preserve the DB, any WAL/SHM files, the safety ledger and existing published
   files on their volume. Do not delete/reset the ledger to resume collection.
3. Run the exporter from a private operator environment:

   ```sh
   uv run --project apps/buycycle python apps/buycycle/migration/export_legacy.py \
     --source /private/operator-copy/buycycle.turso.db \
     --output /private/operator-copy/buycycle-legacy.json \
     --processing-version <verified-legacy-code-sha-or-unknown-legacy>
   ```

The exporter shares the collector lock and copies the database/WAL into a private
temporary directory. Installed Turso has no read-only connection option, so it
opens **only that temporary copy**; it reads the original through read-only file
descriptors. It checks source metadata for concurrent changes, requires the exact
known table set and writes a new mode-0600 output without replacing any file.
Unknown schemas, unreadable ledgers or inconsistent data block the export/import.
The copy itself must have been taken consistently from a fenced source; this tool
cannot retrospectively make an inconsistent copied DB/WAL pair trustworthy.

## Controlled PostgreSQL import

Use a dedicated app database and a release-scoped migrator credential. API startup
does not execute DDL. The runtime role has no schema-creation, table-drop or
truncate authority. The privileged import program is an operator/release step:

```sh
# MIGRATION_DATABASE_URL comes from the approved managed-secret path.
target/nx/buycycle-backend/debug/migrate --grant-runtime
target/nx/buycycle-backend/debug/import-legacy --preview /private/buycycle-legacy.json
target/nx/buycycle-backend/debug/import-legacy --import /private/buycycle-legacy.json
target/nx/buycycle-backend/debug/import-legacy --reconcile /private/buycycle-legacy.json
```

Production uses these entry points from the approved tested image, not a locally
rebuilt executable. Output contains counts and digests, not rows or connection
strings. Preserve the report alongside the release receipt. Do not enable the new
writer until every source count/hash and browser-origin export is accounted for.

Provision the runtime role first. The explicit `--grant-runtime` flag applies the
single canonical `ops/grant-runtime.sql` in a transaction after migration;
missing roles or insufficient owner privileges fail the maintenance step. It
does not create identities or grant schema-changing authority to the runtime.
Local rehearsal's plain `migrate` remains role-neutral. Neither migration nor
grants execute during API startup.

The migration imports current-day proven safety consumption conservatively.
Missing/older state or a pending request holds the entire activation Luxembourg
day at 150/blocked; a later/future ledger date fails. Existing PostgreSQL budget,
block or pending state is never reduced by an import. Recollection starts only
when the durable collector state permits it on a later day.

## Browser-owned state

Database import does not migrate browser storage. Inventory every original
scheme/host/port/device/profile, including both ports 8095 and 8096 and every LAN
or tailnet alias. Export watches, trade logs **and cost assumptions** for bikes
and wheels from each origin before changing URLs or clearing storage. Keep every
original file, including conflicting copies, until reconciliation is approved.

The new UI previews an explicit result and conflict choice before committing it.
The backend checks the authenticated subject, validates the whole state and uses
the expected revision for compare-and-swap. Stale edits return 409. The original
source document and its SHA-256 are archived in `browser_import` in the same
transaction as the new state and `user_state_history` entry. Repeating an exact
unchanged import is safe; a later edit makes the old import conflict rather than
overwriting that edit. Ordinary state writes also retain every acknowledged
revision. Runtime grants preserve those archives as append-only.

## Restore and rollback

A PostgreSQL backup must include all nine application/schema tables, the original
import bundles, browser sources/revisions, collection safety state and retained
source snapshots. Restore it into a separate candidate database. Verify all table
counts/digests before considering activation; restore success alone is not the
gate. Source credentials, backup encryption/custody and Pi volumes need their
separately verified operational controls.

Once any new write exists, Turso is stale. Roll back the application/image while
keeping authoritative PostgreSQL, or recover PostgreSQL forward into a reconciled
candidate. Never restart old Turso as an automatic rollback. A backup taken before
an acknowledged edit is rejected as stale until that edit is recovered. If the
latest source is unavailable, required WAL/PITR and its recovery point must be
proved by the operational plan; this local dump drill does not establish a zero
data-loss disaster-recovery promise.

The synthetic drill uses only the task-owned local PostgreSQL-17 container on
loopback port 5549. It restores every table, introduces a later watch/trade/cost
edit with its journal, rejects the stale candidate, restores a fresh snapshot and
proves the later state survived:

```sh
python3 apps/buycycle/migration/rehearse_restore.py \
  --evidence /private/tmp/buycycle-restore-evidence.json
```

Its container/port/image/database guards reject arbitrary production targets; all
drill databases and temporary dumps are removed after use. The JSON result records
digests and synthetic assertions only. This does not run a restore on the Pi.

## Verification commands

```sh
uv run --project apps/buycycle pytest apps/buycycle/migration/test_export.py -q
BUYCYCLE_TEST_DATABASE_URL=<disposable-test-or-rehearsal-postgres-url> \
  npx nx run buycycle-backend:test
```

PostgreSQL tests require the real engine and create an isolated temporary test
database; they fail rather than substituting SQLite or silently skipping. Legacy
Turso exports are tested against actual temporary Turso databases. No real feed,
notification, payment, user state or production database is used by these checks.
