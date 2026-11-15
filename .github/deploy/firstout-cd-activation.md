# Firstout CD activation record

Status on 15 November 2026: **production rollback baseline verified; automatic
releases remain paused pending a qualified reviewed source**. This record
separates completed operations from the remaining automatic activation. Follow
the [CD runbook](firstout-cd.md) and
[controlled image promotion](firstout-release.md); the canonical decisions remain
[P-006](../../docs/adr/governance.md#p-006),
[P-020](../../docs/adr/data.md#p-020),
[P-045/P-046](../../docs/adr/delivery.md#p-045) and
[P-054](../../docs/adr/operations.md#p-054).

## Verified setup

- GitHub environment `firstout-production` accepts deployments from `main`
  only. Other apps' release environments and holds are unchanged.
- The new Firstout release-tag rules prevent matching tags from being updated
  or deleted. Tags identify source; successful tested-image evidence still
  identifies the artifact to promote.
- Environment secret `FIRSTOUT_RAILWAY_TOKEN` was installed at 08:52:13 UTC;
  authenticated token metadata verifies its Firstout production scope.
  Superseded setup credentials are revoked. No secret value is recorded here.
- Main review ruleset `27305147` is active with no bypass, required code-owner
  review and stale-approval dismissal. Its general approval count remains zero;
  the [CODEOWNERS file](../CODEOWNERS) is now on `main`, so owned files require an
  independent owner's approval. The PR author cannot supply their own approval.
- Firstout PostgreSQL has daily, weekly and monthly backup schedules.
  Pre-090 snapshot `dbc79515-ae59-4bf6-b877-9a6196999119`, created at 09:52 UTC,
  is nonexpiring, reports `referencedMB=786` and passes the live backup gate.
  Earlier snapshot `ad4d3f94` reported `referencedMB=795` and `usedMB=0`.
  Railway's
  [copy-on-write backups](https://docs.railway.com/volumes/backups#pricing) can
  share all data with the source volume, so zero exclusive bytes do not mean an
  empty snapshot. Positive referenced data does not prove successful restoration;
  the separately verified logical-database recovery below has a different scope.
- Merged pipeline source `2d31ed971c635f18dd5487873982d79774ccedf2`
  ([PR #940](https://github.com/F0rge/f0rge/pull/940)) passed
  [main CI](https://github.com/F0rge/f0rge/actions/runs/43695015574) and
  [E2E smoke](https://github.com/F0rge/f0rge/actions/runs/43695015492).
- Exact-source baseline builds succeeded:
  [API run 43695715730](https://github.com/F0rge/f0rge/actions/runs/43695715730)
  and [frontend run 43695719281](https://github.com/F0rge/f0rge/actions/runs/43695719281).
  Their trusted artifacts identify
  `ghcr.io/f0rge/firstout-api@sha256:9072596ac45b8429fb0d5fc8227cc31395bf2a3db2bf2fcd3d354f66eae59713`
  and
  `ghcr.io/f0rge/firstout-frontend@sha256:7e462a7328cb4998c9c297fa06931d3dfefec62b0f64261e29367a9eac280860`.
  The API digest was pulled anonymously. Subsequent production serving-version
  verification is recorded below; publication alone did not establish it.
- The published API and the actual old 089 image passed the PostgreSQL 18
  compatibility harness: migration/replay, authenticated HTTP, and old-image
  reads of new-version writes. These tests used isolated synthetic data.
- [PR #942](https://github.com/F0rge/f0rge/pull/942) merged as
  `d2c5fd2f2ec81268f7af6d41d1ae227a7d98eb60`. It adds the ownership controls,
  corrects the snapshot gate to check referenced data, and aligns the automatic
  migration rehearsal with PostgreSQL 18. Its
  [main CI](https://github.com/F0rge/f0rge/actions/runs/43698244488) and
  [E2E smoke](https://github.com/F0rge/f0rge/actions/runs/43698244559) passed.
  Activation-change verification also passed 30 controller tests, 94 release
  unit tests and 11 CD pipeline tests. This is source validation; it does not
  establish a successful automatic release.

### Isolated provider rehearsals

- The tested API image was deployed to a temporary service using synthetic
  variables, application lifespan disabled, and no database, public domain or
  volume. Its provider digest and one running replica matched the artifact.
  HTTP health returned 200 with `no-store`; this checks image/provider identity,
  not normal startup or production database readiness.
- Intentionally failing readiness deployment
  `1665ac20-48f4-4020-969b-8b1f4cb0c681` failed while healthy deployment
  `d3c36c7e-f9c8-457d-b304-173b2ffdd5d6` remained available. Operator recovery
  deployment `520ba9e4-d55d-4351-9381-6a71863de368` restored the expected API digest
  with one running replica and verified health.
  This was an operator-run failure/recovery rehearsal, **not execution of the
  automatic CD rollback controller**.
- Frontend deployment `98f358dd-9aab-46a5-a686-6e66ceb54521` also verified the
  tested image's exact digest, one running replica and HTTP 200 with `no-store`.
- Both temporary services were deleted after their outcomes were verified.
  Private provider receipts retain their deployment identities.

### Logical database recovery

- After the concurrent data replacement committed, a full, unfiltered native
  backup of Firstout's database and roles was saved as a private AES-GCM
  encrypted artifact and restored into isolated PostgreSQL 18. Both native
  database restoration and role restoration completed with exit code zero.
- The first restored database reached `089_merge_record_workspaces`. Metadata
  checks confirmed `firstout_app` is a non-owner, `NOSUPERUSER`, `NOBYPASSRLS`
  role without membership permitting a privileged role assumption. These role
  flags alone did not establish read-only migration-metadata permissions.
- At 10:24 UTC, a new saved encrypted full-database-and-role archive from the
  completed 090 baseline also restored successfully into isolated PostgreSQL
  18. Its exact source/schema/policy receipt and read-only runtime metadata
  permissions were preserved. The recovery container was removed afterward.
- The recovery container had no network, published ports or application
  process. This rehearsal made no production writes; its container cleanup was
  verified. Independent data review checked the recovery script and metadata.
- This establishes logical database-and-role recovery at that checkpoint. It
  does **not** establish photo/bucket recovery or provider-snapshot restoration.
  Archive contents, business row counts, credentials, encryption key and private
  recovery receipts are not included in this public record.

## Review protection in this change

The [CODEOWNERS file](../CODEOWNERS) assigns Firstout source, its shared backend
dependencies and build inputs to the two existing maintainers. It is now merged,
and the configured main rule enforces independent code-owner review. The rule
and ownership file are separate controls; both are required.

Shared workflows, actions, scripts and deployment helpers also require review:
another workflow could request the `firstout-production` environment and copy
its deployment credential elsewhere. Reviewing only `cd-firstout.yml` would
leave that path open. All Firstout source is covered because a later reviewed
release includes earlier changes already on main. The shared-library and root
build rules affect other apps only where those files are also Firstout inputs.
Nx evaluates workspace project metadata and executable plugin configuration
before selecting tasks, so those configuration files also require review.
Other apps' business source and release authorization remain unchanged.

## Production rollback baseline verified

- Concurrent authorized Primavera maintenance performed the historical upgrade
  from `083_portal_clerk_identity` to `089_merge_record_workspaces` and committed
  its data replacement. This activation task then rechecked production before
  the controlled 090 migration and image promotion.
- At 10:00 UTC, trusted-image job `a40a5d1c-310b-4f13-908b-608e115ec197` ran the
  packaged 090 migration and a separately reviewed operator permission
  correction. Both phases succeeded. The receipt binds source
  `2d31ed971c635f18dd5487873982d79774ccedf2`, revision
  `090_release_migration_receipts` and policy
  `b3a7954e956a8e60bbeee13efaeaa600755a866529aeece3fe63ddfff10b3bc2`.
- The published `9072596a…` image's runner alone **did not** remove existing
  runtime write grants on migration metadata. The operator correction revoked
  runtime/PUBLIC privileges on both metadata tables and granted runtime SELECT.
  These were two database transactions; image promotion remained held until
  hardening and fresh runtime verification succeeded. The verified application
  baseline includes this explicit correction; it does not certify that image's
  runner as sufficient by itself.
- Fresh runtime checks established metadata SELECT access and no checked
  metadata write privileges, including inherited or assumable paths. An
  independent query through the live API confirmed Alembic UPDATE is denied
  while existing default business-table DML remains available. This PR fixes
  the runner so metadata permission hardening commits atomically with migration
  and receipt creation. PostgreSQL regressions include restricted runtime,
  forced-RLS/cross-tenant denial and no administrator credential in the strict
  PostgreSQL 18 image probe; future normal CD needs no operator correction hook.
- API deployment `fb3793a0-dd25-4511-83c9-eaf34e4ee557` serves the exact
  `9072596a…` digest with one `RUNNING` replica and provider rollback support.
  `/api/v1/ready` returned HTTP 200 with `no-store`, exact source above, schema
  090, image/receipt schema 090, matching policy and `migration_receipt=true`.
  The fixed provider target, disabled image updates, absent Git triggers and
  cleared legacy start/pre-deploy hooks were verified.
- Frontend deployment `92c0c294-da60-447f-aca3-e4b89aa59459` serves the exact
  `7e462a73…` digest with one `RUNNING`, rollback-capable replica. Health returned
  HTTP 200 with `no-store`; served JavaScript and CSS hashes matched the exact
  tested image.
- `FIRSTOUT_BOOTSTRAP_BACKEND_IMAGE` now equals the verified serving API digest.
  The one-time migration job was deleted after its outcome was verified; no
  task-owned ephemeral service remains.
- The saved 090 logical database-and-role restore described above verifies the
  receipt and restricted metadata permissions survive recovery. This is SQL
  archive recovery, not provider-volume or photo/bucket restoration. Application
  rollback keeps the expanded schema and new transactions; it never restores
  either database backup automatically.

## Automatic activation pending

The authorized [pause issue #941](https://github.com/F0rge/f0rge/issues/941)
remains open. PRs #940 and #942 have no qualifying GitHub approval on their final
heads. Their merges and green checks do not satisfy the current automatic source
gate, which requires an `APPROVED` record from a non-author with repository
write, maintain or admin permission. P-005's independent agent review and CI are
separate requirements; this chat's operations authorization also cannot create
that GitHub review record. The
[automatic run for #942](https://github.com/F0rge/f0rge/actions/runs/43698452247)
stopped before deployment.

Obtain the qualifying GitHub approval on this activation PR's final head and
merge it to `main`. Once the reviewed runner correction and prerequisites are
verified, reconcile the pause issue and observe successful CI followed by the
actual automatic CD run. The installed production credential has not yet been
exercised by a successful GitHub Actions deployment. Retain the resulting
release journal, running image digests,
readiness/migration receipt, served assets and recovery-test evidence before
claiming activation complete. Distinguish controller tests using synthetic
provider responses from the isolated operator recovery above; neither alone
establishes automatic production rollback execution.

Keep credentials and private recovery receipts outside this public repository.
Update this checkpoint as each operation is verified; do not infer completion
from a queued workflow, configured secret, snapshot schedule or HTTP liveness.
