# Primavera data replacement

This is the operator handoff for the prepared Cin7 replacement of the Primavera
organisation. The user authorised this replacement, exact fractional stock, and
the reviewed location mapping. That authorisation does not approve a production
release of the new application source. The current work is preparation: no
replacement or release has been performed.

Use the reviewed prepared package and source-bin mapping, kept in private
operator storage outside this public repository. Do not import the raw export,
recursively load a package directory, or load review/reference files as live
transactions. Retain the original export and all cleaning/staging evidence.

## What the prepared replacement contains

The approved cleaning scope is current operations plus the last 24 months of
searchable history, using the fixed 14 November 2024–14 November 2026 window
for the four history files. Older unresolved records are withheld for
reconciliation; history is not evidence of a live receivable, payable or stock
commitment.

| Area | Prepared outcome |
| --- | --- |
| Customers | 510 masters: 41 active and 469 archived; 558 contacts and 965 addresses. |
| Suppliers | 190 masters: 77 active and 113 archived; 114 contacts and 54 addresses. |
| Products | 2,731 products. Exclude only the exact product code `AU0001`; retain the other 52 fabric products. Preserve the source's 23 products marked not for sale. |
| Stock | 1,759 source rows aggregate to 1,758 unique SKU/bin balances. Preserve all 17 fractional stock rows exactly, with up to four decimal places. |
| Locations | Apply the reviewed Bedfordview, Kramerville, Warehouse and Unassigned mapping; Unassigned holds eight units. Four location names change and six unused locations become archived. Existing location/bin IDs and settings references remain stable. |
| Sales history | 1,329 sales documents and 1,294 sales orders, imported as archives. |
| Purchase history | 77 purchase documents and 50 purchase orders, imported as archives. |
| Pricing | Retain all five source tiers as reference data, including tier 450. Activate only the four recognised customer-class price lists: 10,259 valid items. |
| Contacts/addresses | Hold one orphan contact in audit evidence; deduplicate four exact duplicate addresses. Do not invent missing contact values. |
| Assemblies/costs | Withhold 23 recipes linked to excluded AU0001 products. Retain four fractional BOMs; existing whole-kit sale/pick flows reject these explicitly. Seven unknown unit costs remain null and block COGS-dependent sales until corrected. |

Archived customers and suppliers remain searchable in their Archived lists and
can be restored. They do not appear as normal choices for new transactions.
Source sellability is independent of stock: a product marked not for sale may
hold stock, but the till excludes it and rejects its barcode scan.

The archive loader creates no journals, payments or stock movements from history,
and does not turn historical orders into live commitments. It retains canonical
source rows on the five archive document parents. Credit references leave 616
sales documents unverified; they are not posted as financial balances. Thirty
older open documents remain withheld. Reference sales summaries, payments and
movement reports must not be replayed, which would duplicate activity.

## Application and schema prerequisites

The replacement requires exact schema head `087_cin7_archive_provenance` and a
compatible API and frontend before fractional rows are loaded.

| Migration | Change and recovery constraint |
| --- | --- |
| 084 | Adds customer/supplier archive flags, active by default. The replacement applies the reviewed active/archive split. |
| 085 | Changes ten inventory, stocktake, adjustment, transfer, PO and bill quantity columns to `Numeric(14,4)`. Downgrade refuses fractional or out-of-range values rather than rounding. |
| 086 | Adds `skus.is_sellable`, true by default for existing products. A downgrade would remove that information. |
| 087 | Adds canonical Cin7 JSON payloads to five archive parents and limits supplier-reference uniqueness to live bills. Downgrade refuses retained payloads or references incompatible with the previous index. |

Follow the [Firstout tested-image release procedure](../../../.github/deploy/firstout-release.md).
Its API and frontend profiles are fixed; the API image never migrates on startup.
Apply migrations through the separately controlled migration operation, retain
the evidence, and promote the tested compatible images. Do not use a legacy
source rebuild, `railway up`, an unreviewed command override or a hotpatch to
bypass artifact verification. Publication, merge, CI and this guide grant no
release permission.

## Replacement command and safeguards

The implementation is
[`replace_primavera.py`](../backend/app/commands/replace_primavera.py), using the
strict [`prepared.py`](../backend/app/services/cin7_import/prepared.py) adapter.
It accepts exactly 14 candidate files and verifies three additional evidence
files. The manifest, each allowed file and the bin mapping must match their
reviewed SHA-256 hashes; unexpected file sets or changed row shapes/counts fail.

The command is restricted to the fixed Primavera team identity, exact database
name, schema 087, maintenance status and verified non-owner runtime role under
FORCE RLS. It rejects an active import, unknown table inventory and nonempty
protected portal/commerce dependencies that would make replacement unsafe.

Business deletion and loading run in one transaction. Protected identity,
membership, roles, settings and accounting configuration are fingerprinted;
other organisations are checked through masked fingerprints. The planned
location changes are explicit. Selected existing SKU UUIDs, external publication
bindings and photos are retained, including six externally published products.
There is no global truncate, bucket deletion, provider operation, email send or
background job in this command.

Run from `apps/firstout/backend` with the approved private connection already
configured. The variables below are operator-supplied paths/hashes and the
verified database name; they are not credentials. No `--dry-run` flag exists:
omitting `--commit` performs the full replacement and validation, then rolls
back. Capture stdout in a private, access-restricted plan file.

```bash
umask 077
.venv/bin/python -m app.commands.replace_primavera \
  --package "$PRIMAVERA_PACKAGE_DIR" \
  --team-id "$PRIMAVERA_TEAM_ID" \
  --manifest-sha256 "$PRIMAVERA_MANIFEST_SHA256" \
  --bin-map "$PRIMAVERA_BIN_MAP" \
  --mapping-sha256 "$PRIMAVERA_MAPPING_SHA256" \
  --expected-database "$PRIMAVERA_DATABASE" \
  > "$PRIMAVERA_PLAN"
```

Check the successful exit status and review `committed: false`,
`dry_run_rolled_back: true`, target/database/schema/package/mapping identities,
the baseline hash, protected/other-organisation fingerprints, deletion counts,
retained SKU IDs, location changes and load results. A failed command exits 2;
its refusal is not a completed dry run. The database must match this baseline
again when committing.

Commit additionally requires a reviewed plan and independently prepared backup
evidence, each bound by its exact file hash. The evidence fields currently
checked are `team_id`, `database`, `before_sha256`, `restore_verified: true`,
`writes_drained: true`, `provider_project_id`, `provider_service_id`,
`backup_path` and `backup_sha256`. The backup must be nonempty and its bytes must
match the checksum. These fields record independently established facts; setting
a boolean or supplying an ID does not itself drain writers, verify a provider
identity or prove a restore. Retain the underlying receipts privately.

After all release and replacement prerequisites below are met, the same command
uses these additional flags:

```bash
  --commit \
  --reviewed-plan "$PRIMAVERA_PLAN" \
  --reviewed-plan-sha256 "$PRIMAVERA_PLAN_SHA256" \
  --backup-evidence "$PRIMAVERA_BACKUP_EVIDENCE" \
  --backup-evidence-sha256 "$PRIMAVERA_BACKUP_EVIDENCE_SHA256"
```

The commit compares its protected state, other organisations, deletions,
retained SKU IDs, location changes and load result to the reviewed rolled-back
plan. A mismatch rolls the whole transaction back. Retain successful stdout and
verify `committed: true` before treating the replacement as committed. If the
process loses its response, inspect current database state and retained evidence
before retrying; do not assume failure means no commit.

## Evidence and remaining work

Evidence reported during preparation on 14 November 2026:

| Check | Observed result and limits |
| --- | --- |
| Prepared data | Original cleaning package: 82 checks. Staging: 50 parent-document hashes and 42 checks, plus ten independent data checks and seven independent numerical checks. Private evidence remains outside Git. |
| Recovery rehearsal | Encrypted target backup at source schema 083 covering 87 tables and 122,408 rows restored exactly into isolated PostgreSQL 18, without networking, app processes or SMTP. This is an earlier recovery rehearsal, not the fresh pre-commit backup. |
| Backend | 218 feature tests reported passing before additional replacement/security matrix work. Final replacement tests and independent security fixes/review remain in progress. |
| Frontend | 153 tests, strict type checking, focused lint and Next production build reported passing. |
| Live UI/API | Seven grouped checks passed through actual Carbon pages in a built Vite fixture, real FastAPI/SQLAlchemy/PostgreSQL and a signed synthetic Clerk boundary. Desktop adjustment/stocktake/transfer, mobile fractional count/transfer, explicit zero versus blank, failure/retry and nonsellable till behaviour passed; no browser errors or unexpected API 500s. This is not a full Next server, real Clerk or production grant audit. |
| Release preparation | Ten delivery tests and 24 DevOps groups reported passing for the extended closed component profiles. Actual API image build/container smoke and CI for this final source have not yet been established. No release was performed. |

A pre-existing WMS limitation remains outside this replacement: dispatch reloads
the transfer tab and resets its inbound destination to the standing location.
Reselect the receiving location to see and receive the transfer. Exact stock
values were verified despite that reset.

Before any production replacement write:

1. Finish the final backend/replacement test matrix, security corrections and
   independent QA, backend/data, security, delivery and DevOps review. Retain
   their actual final results and complete CI for the selected source.
2. Build and smoke-test the exact API/frontend release artifacts. Obtain Leo's
   explicit consent for the selected commit/digests/targets and verify their
   release/provider evidence; do not infer it from the data-replacement request.
3. Recheck the actual Firstout target and runtime/migration grants, establish
   maintenance, drain all writers and jobs, and take a fresh encrypted backup.
   Verify its restore and bind the evidence to the reviewed baseline. The
   earlier backup does not cover subsequent changes.
4. Complete the controlled migrations and compatible application releases,
   verify schema 087 and health, then run and independently review the final
   replacement dry run against the fenced target. Reconcile any changed
   baseline and backup before commit.
5. Commit only the reviewed package/mapping/plan. Check archive partitions,
   product exclusions/sellability, exact location/bin stock, prices, withheld
   items, retained photos/publication bindings, protected records and other
   organisations. Walk through the deployed app before reopening writes.

Source photo retrieval is incomplete: automatic approval review rejected the
proposed retrieval because source URLs contain tokens. User permission for that
retrieval remains pending. Do not publish those URLs/tokens or claim the export's
photos have been imported; preserve existing retained photos meanwhile.

## Recovery

A validation failure before commit rolls the transaction back. Keep maintenance
and retain the refusal, plan and backup evidence while resolving it.

After commit, stop writes if reconciliations or deployed journeys fail. Use the
reviewed recovery plan and verified backup under controlled migration/runtime
roles, preserving the failed-state evidence. Restore only the intended scope;
never overwrite other organisations as an implicit rollback. Recheck identities,
protected settings, stock/bin totals and archived history before reopening.

Do not serve fractional data through an older integer-only API. Do not drop
sellability or canonical source payloads to make a downgrade succeed. Prefer a
reviewed compatible forward fix, or restore the verified pre-replacement data
before any separately reviewed schema/application rollback. A provider rollback
or successful restore command alone is not evidence of business recovery.
