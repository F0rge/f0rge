# Buycycle operational readiness

The migration implementation is prepared for review. **Production is not yet
proved ADR compliant and has not been cut over.** No provider configuration,
production data import, merge or release is performed by this evidence document.

| Area | Evidence available | Remaining production gate |
| --- | --- | --- |
| Private runtime | Compose has no app ports; API verifies signed Access identity; local fake identity and direct-origin denial are tested. | Create/verify the actual owner-only email-code Access app, tunnel and DNS; test signed-in and denied identities on the deployed service. |
| Pi/provider identity | Coordinator read the existing tailnet Pi and old HTTP services on 8095/8096; both legacy pages responded. | Recheck engine ID, ARM64, volumes, one PostgreSQL cluster/network and provider identities immediately before an authorized cutover. |
| Release approval | Coordinator read GitHub production settings: sole Leo reviewer, self-review prevented, administrator bypass disabled and main-only deployment policy. Source release-helper tests cover fixed artifact/target, expiry, replay and receipt binding. | Install/verify the separate requester GitHub App, activate immutable release-tag protection and managed mTLS Pi agent. An approval setting alone does not fence direct provider credentials. |
| Provider preflight | `ops/test_preflight.py` exercises documented provider schemas, exact owner/audience/OTP policy, tunnel/DNS, Docker engine, old-writer fence, grants and secret custody; negative observations refuse a passed receipt. | Run actual scoped read-only provider/PG/secret observations on the staged Pi. No live provider receipt exists for the proposed new service. |
| PostgreSQL migration | Coordinator's isolated actual-engine tests and cross-language rehearsal preserved synthetic source records/hashes. Evidence: `/private/tmp/buycycle-cross-language-rehearsal.json`. Explicit migration and runtime grants have separate credentials. | Fence old writers; preserve the real DB/WAL/ledger and every browser origin; import/reconcile every real record and prove runtime/migrator grants on the selected existing cluster. |
| Browser state | Local production frontend/API tests cover owner-bound import, preview, conflict and persistence. | Export/reconcile bikes and wheels watches, trades and cost assumptions from every device/profile and LAN/tailnet/origin alias before changing URLs. |
| Restore | Two synthetic drills passed: the PostgreSQL restore reconciled every table and rejected a stale candidate after a later edit (`/private/tmp/buycycle-restore-rehearsal.json`); `backup.py` streamed PostgreSQL 17.12 through age 1.2.1 and decrypted directly into a separate restore, reconciling all nine schema tables and denying backup-role writes, DDL and cross-app access (`/private/tmp/buycycle-encrypted-backup-rehearsal.json`). The encryption drill used fixture data and a dirty source tree. | Prove protected production backup custody, encryption/decryption, scheduling, off-device storage and a real candidate restore. Agree the required recovery point and prove WAL/PITR where needed. Local fixture drills do not establish those controls or approval of an exact release artifact. |
| Exact artifact | The image rehearsal builds/probes a production `linux/arm64` archive with synthetic services; release code promotes the archive and verifies the canonical config digest and running container identity. | Final clean-commit image evidence, successful main CI, approved registry digest and receipts, then observed running image/readiness after explicit release approval. Dirty exploratory images cannot release. |
| Logs and capacity | Structured source logging omits identities/credentials; Docker log rotation and app/database/connector resource bounds are configured. Raw snapshots and journals have no automatic purge. | Verify Pi logs/redaction, disk/volume capacity, backup freshness and monitor delivery. The configured 768 MiB/1 CPU values are test settings, not approved SLOs or production sizing evidence. |

The current Cloudflare account contains other private applications and an existing
owner policy. Those are inventory; none proves Buycycle is protected. Proposed
`buycycle.leo-figueiredo.com` is a protected route, with no published origin ports.
The old service and its data remain untouched while the PR is reviewed.

Follow [the operations procedure](../ops/README.md) for exact local checks,
configuration, cutover fences and provider receipt generation, and
[data migration and recovery](data-migration.md) for import/reconciliation and
rollback. Missing live evidence stays an explicit release block. P-010's agreed
Buycycle-first sequence changes pilot ordering; it does not waive these gates.
