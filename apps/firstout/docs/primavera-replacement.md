# Primavera data replacement

This is the operator handoff for the prepared Cin7 replacement of the Primavera
organisation. The user authorised this replacement, exact fractional stock, and
the reviewed location mapping. That authorisation does not approve a production
release of the new application source. Application source `b7d5063a` and schema
088 are prepared and tested locally; no production replacement or release has
been performed.

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
| Sales history | 1,329 sales documents: 1,297 invoices and 32 credit notes, plus 1,294 sales orders, imported as archives. |
| Purchase history | 77 purchase documents and 50 purchase orders, imported as archives. |
| Pricing | Retain the source tiers as reference data, including 450 positive prices in tier 5. Activate only the four recognised customer-class price lists: 10,259 valid items. |
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

The replacement requires exact schema head `089_merge_record_workspaces` and a
compatible API and frontend before fractional rows are loaded.

| Migration | Change and recovery constraint |
| --- | --- |
| 084 | Adds customer/supplier archive flags, active by default. The replacement applies the reviewed active/archive split. |
| 085 | Changes ten inventory, stocktake, adjustment, transfer, PO and bill quantity columns to `Numeric(14,4)`. Downgrade refuses fractional or out-of-range values rather than rounding. |
| 086 | Adds `skus.is_sellable`, true by default for existing products. A downgrade would remove that information. |
| 087 | Adds canonical Cin7 JSON payloads to five archive parents, permits unknown PO factory amounts as null, and limits supplier-reference uniqueness to live bills. Downgrade refuses retained payloads, null factory amounts or references incompatible with the previous index. |
| 088 | Widens eight sales VAT/gross columns to `Numeric(16,4)` while retaining the previous twelve integer digits. This preserves 288 source rows across 166 documents with subcent amounts. Live sales still calculate and return cents; archive screens show up to four decimals. Downgrade locks all four affected tables and checks all organisations, refusing any non-cent, nonfinite or out-of-range amount. |
| 089 | Merges the existing inventory/history branch at 088 with record workspaces at 085. Both branch identities stay unchanged; the merge itself performs no DDL or data changes. Replacement preserves workspace operation receipts for Primavera and every other organisation. |

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
The loader parses the verified CSV bytes with newline preservation, keeping
meaningful LF/CRLF inside quoted fields. Splitting CSV into physical lines or
normalising those field values would change addresses and their identity hashes;
the required customer-address result is all 965 prepared rows, not an extra
"normalised duplicate" removal. Typed Decimal signatures also keep valid
re-import comparisons independent of decimal scale representation.

The command is restricted to the fixed Primavera team identity, exact database
name, schema 089, maintenance status and verified non-owner runtime role under
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
| Recovery rehearsal | The original encrypted schema-083 backup restored exactly: 87 tables and 122,408 rows in isolated PostgreSQL 18, without networking, app processes or SMTP. A separate recovery drill after a local replacement restored all 91 tables and 122,412 baseline rows with matching before-hashes. These drills do not replace the fresh pre-commit backup. |
| Final package rehearsal | Source `b7d5063a` passed against a fresh private database restored from the verified schema-088 backup. The full dry run left all 91 tables unchanged after rollback; the reviewed local replacement committed successfully, then passed complete post-read verification. No production writes, API process or jobs ran against this private copy. |
| Final source fidelity | All four history files matched canonical source row counters. Every invoice/credit parent and line Tax/Total matched exactly to four decimals, and all quantities matched. Contacts 558/114 and addresses 965/54 matched exact payload sets and values, including quoted newlines. Customer/supplier archive splits, 2,731 products, 23 not-for-sale flags and all 2,731 retained SKU UUIDs matched; six published products remained published. |
| Final stock and isolation | Exact per-SKU/bin stock total: 4,078.5100 units, comprising Warehouse 2,961.5100, Bedfordview 672, Kramerville 437 and Unassigned 8. Imported counts: 1,297 invoices, 32 credit notes, 1,294 SOs, 77 bills and 50 POs. Payments, journals, outbox and newly created operational documents were zero; protected and other-organisation fingerprints were unchanged. |
| Backend | Fifty affected integration tests passed after the strict Decimal idempotency and quoted LF/CRLF CSV fixes, including four new regressions. The final 883-test full-suite run and CI result are tracked in the PR evidence; the scoped 50-pass run is not substituted for either. |
| Independent reviews | Backend, data, security, frontend, DevOps and delivery signoffs completed for the final source. Two additional security/parser regressions passed. Review is evidence, not production-release permission. |
| Frontend | 159 tests, strict type checking, full lint and Next production build reported passing. Four existing image-element warnings remain in frontend lint; no new lint errors were reported. |
| Live stock UI/API | Seven grouped checks passed through actual Carbon pages in a built Vite fixture, real FastAPI/SQLAlchemy/PostgreSQL and a signed synthetic Clerk boundary. Desktop adjustment/stocktake/transfer, mobile fractional count/transfer, explicit zero versus blank, failure/retry and nonsellable till behaviour passed; no browser errors or unexpected API 500s. |
| Live history UI/API | Eight groups passed again after the 088 precision fix, with real PostgreSQL 16 and the same synthetic signed identity boundary, without HTTP mocks. Unknown SO amounts remain unknown; PO quantity 4.576 and original Cost `100.1234567890123`/Total `100.00` retain their precision without an invented currency. Invoice totals 100/15/115 and foreign bill USD 100 remain visible while settlements and missing FX/ZAR are labelled unknown/not imported. Operational invoice/bill lists exclude archives and link to working history searches; direct detail URLs and a 390px bill layout passed. |
| Live archive guards | Five real HTTP 409 rejections, rerun after 088: invoice PDF, invoice payment, bill payment, SO invoicing and PO on-water action. Payment, journal, outbox and SO-payment counters stayed unchanged. No browser errors or unexpected API failures; the unconfigured local Ops Commerce endpoint returned its expected 503 configuration response. |
| Live archive precision | Three additional groups passed through the actual API/UI: invoice tax `15.0015` and gross `115.0015`, signed credit tax/gross `-20.0015`/`-120.0015`, and twelve-digit gross `999999999999.1234` remain exact. History exposes a Tax column; original cents still show two places. Two additional precise-invoice PDF/payment requests returned HTTP 409 with unchanged counters. Source-file hashes and screenshots identify the tested frozen tree. |
| Release preparation | Eleven delivery tests and 26 release-helper groups passed for the closed component profiles. The final `b7d5063a` Linux/amd64 API image passed packaged smoke against PostgreSQL 18, including FORCE RLS and normal startup; the private receipt is `api-image-smoke-final-b7d5063a.json`. CI and selected API/frontend artifact-release verification remain distinct prerequisites. No release was performed. |

The browser evidence uses the built Vite fixture with actual Carbon pages,
AuthProvider and a navigation adapter, not the real Next server or real Clerk.
It does not certify production runtime grants or a complete accessibility audit.
No original attachment was seeded for the history walkthrough, so retained-file
download was not exercised. Screenshots and reports stay in private local
artifacts outside Git.

A pre-existing WMS limitation remains outside this replacement: dispatch reloads
the transfer tab and resets its inbound destination to the standing location.
Reselect the receiving location to see and receive the transfer. Exact stock
values were verified despite that reset.

The invoice paper also has an existing mobile clipping limitation. At 390px,
the unchanged Carbon table minimum and parent sizing produce the same clipped
paper for cents-only and four-decimal invoices; the precision formatter adds no
width. The body itself does not overflow, but the main content clips the paper
instead of containing it in a useful table scroller. No mobile invoice visual
pass is claimed. The 390px bill detail and mobile stock flows passed.

Before any production replacement write:

1. Retain the final full-suite, CI, independent-review and local rehearsal
   evidence for the selected source. Recheck required CI before release; scoped
   tests and an earlier image receipt do not replace that evidence.
2. Build and smoke-test the exact API/frontend release artifacts. Obtain Leo's
   explicit consent for the selected commit/digests/targets and verify their
   release/provider evidence; do not infer it from the data-replacement request.
3. Recheck the actual Firstout target and runtime/migration grants, establish
   maintenance, drain all writers and jobs, and take a fresh encrypted backup.
   Verify its restore and bind the evidence to the reviewed baseline. The
   earlier backup does not cover subsequent changes.
4. Complete the controlled migrations and compatible application releases,
   verify schema 089 and health, then run and independently review the final
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
