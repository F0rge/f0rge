# Firstout CD activation record

Status on 15 November 2026: **setup in progress; automatic production releases
remain paused**. This record separates configured controls from the remaining
production work. Follow the [CD runbook](firstout-cd.md) and
[controlled image promotion](firstout-release.md); the canonical decisions remain
[P-006](../../docs/adr/governance.md#p-006),
[P-020](../../docs/adr/data.md#p-020),
[P-045/P-046](../../docs/adr/delivery.md#p-045) and
[P-054](../../docs/adr/operations.md#p-054).

## Verified configuration

- GitHub environment `firstout-production` accepts deployments from `main`
  only. Other apps' release environments and holds are unchanged.
- The new Firstout release-tag rules prevent matching tags from being updated
  or deleted. Tags identify source; successful tested-image evidence still
  identifies the artifact to promote.
- Environment secret `FIRSTOUT_RAILWAY_TOKEN` was installed at 08:52:13 UTC;
  authenticated token metadata verifies its Firstout production scope.
  Superseded setup credentials are revoked. No secret value is recorded here.
- Main review ruleset `27305147` is active with no bypass, required code-owner
  review and stale-approval dismissal. The original activation checkpoint had a
  zero general approval count; the publisher setup strengthened it to **one**
  while retaining the other review protections. Existing main ownership is
  enforced. The new global Leo-only ownership remains pending its reviewed
  source merge; see [the publisher checkpoint](../../docs/agents/github-publisher.md#verified-checkpoint-15-november-2026).
- Firstout PostgreSQL has daily, weekly and monthly backup schedules. Its
  fresh, nonexpiring snapshot `ad4d3f94` reports `referencedMB=795` and `usedMB=0`
  and passes the corrected live backup gate. Railway's
  [copy-on-write backups](https://docs.railway.com/volumes/backups#pricing) can
  share all data with the source volume, so zero exclusive bytes do not mean an
  empty snapshot. Positive referenced data does not prove successful restoration;
  this activation task has not performed a restore rehearsal.
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
  The API digest was pulled anonymously. Publication does not establish the
  images currently serving production.
- The published API and the actual old 089 image passed the updated PostgreSQL
  18 compatibility harness: migration/replay, authenticated HTTP, and old-image
  reads of new-version writes. These tests used isolated synthetic data.

## Review protection in this change

The prepared [CODEOWNERS file](../CODEOWNERS) assigns every repository path to
Leo as the sole required code owner, retaining coverage of Firstout source,
shared backend dependencies and build inputs. It replaces the older two-owner
file only after the reviewed change reaches protected `main`; the live file can
still request Luis until then. The configured main rule still requires actual
code-owner approval. The bot authors PRs and Leo personally reviews them;
agents do not submit his approval. See the [publisher and native merge procedure](../../docs/agents/github-publisher.md)
and canonical [P-005](../../docs/adr/governance.md#p-005). Repository auto-merge
availability alone does not activate the new default or arm a PR.

Shared workflows, actions, scripts and deployment helpers also require review:
another workflow could request the `firstout-production` environment and copy
its deployment credential elsewhere. Reviewing only `cd-firstout.yml` would
leave that path open. All Firstout source is covered because a later reviewed
release includes earlier changes already on main. The shared-library and root
build rules remain Firstout inputs; the new global ownership rule also covers
other apps' source for human review.
Nx evaluates workspace project metadata and executable plugin configuration
before selecting tasks, so those configuration files also require review.
Other apps' release authorization remains unchanged under P-006.

## Work still required

- Keep the authorized [pause issue #941](https://github.com/F0rge/f0rge/issues/941)
  open until activation prerequisites and the serving baseline are verified.
- Concurrent authorized Primavera maintenance advanced production from
  `083_portal_clerk_identity` through `089_merge_record_workspaces`. That upgrade
  was not performed by this activation task. Wait for its cutover to finish and
  recheck production state before running the pinned CD-aware image's command
  for `090_release_migration_receipts` or promoting either baseline image.
  Preserve backup, restore-rehearsal, role and migration evidence; never use the
  test-database bootstrap option in production.
  The concurrent maintenance's tenant-scoped logical backup does not establish
  whole-database recovery. Retain a full-database backup and verify isolated
  restoration after that cutover before the 090 baseline operation.
- Verify pinned, actually serving API and frontend images. The API must expose
  database-backed `/api/v1/ready` with its exact source, schema, policy and
  completed receipt. Set `FIRSTOUT_BOOTSTRAP_BACKEND_IMAGE` to that verified
  serving API digest. An older 089 image cannot provide this baseline.
- Verify alternate provider triggers are disabled, pending provider changes are
  reconciled, and the recovery rehearsal succeeds using isolated resources.
  Isolated API rehearsal service `d0465656` reached deployment `f11581d7`
  `SUCCESS` with one healthy replica, the expected API digest above, and HTTP 200
  with `no-store`. It uses synthetic variables, application lifespan disabled and no
  database, domain or volume. This proves the temporary target's image/provider
  identity, not normal startup, production database connectivity or readiness.
  Its bad-health/recovery rehearsal is still pending a verified outcome.
- Obtain an independent authorized GitHub approval on a new PR's final head,
  merge to `main`, and observe successful CI followed by the automatic CD run.
  PR #940 has no GitHub approval record, so it cannot pass the automatic source
  gate. Record the resulting release journal, immutable image identities,
  readiness, assets and recovery evidence before claiming activation complete.

Keep credentials and private recovery receipts outside this public repository.
Update this checkpoint as each operation is verified; do not infer completion
from a queued workflow, configured secret, snapshot schedule or HTTP liveness.
