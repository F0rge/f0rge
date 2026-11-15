# Buycycle migration verification

This is evidence for the implementation PR, not a certification of the running
legacy Pi service. No production data was imported, and no merge or deployment
was performed. All fixtures below are synthetic.

| Boundary | Verification |
| --- | --- |
| Data preservation | Actual Turso export into Rust/PostgreSQL, exact five-table keys/content/count reconciliation, repeated import and conflict rejection. Unknown columns, nulls and original money units survive. |
| Recovery | Actual PostgreSQL restore reconciles all nine app tables; a later acknowledged edit makes the earlier candidate stale and blocks activation. A separate restricted-role PG17 dump streamed through age, decrypt and restore also reconciles nine synthetic tables; write, DDL and cross-app connection were denied. |
| Rust API and collector | Real PostgreSQL tests, 54-row legacy metric characterization, durable quota/lock/block failure cases, atomic writes and replay provenance. Shared signed-identity and error-envelope tests cover denied identity, malformed input and private errors. |
| Frontend | Nx lint/typecheck/test/build/codegen checks and shared Primer Storybook build. Twelve Chromium cases cover denied, loading, empty, error, saved, stale, partial, conflict, import, identity-change races and mobile keyboard behavior. Ten axe scans cover the tested desktop/mobile views. |
| Integrated walkthrough | The production React build called the actual Rust API and PostgreSQL through a local RS256 identity gateway. Both categories and market insights loaded; a watch survived reload; a cost edit persisted; negative costs showed a labelled validation error. Direct origin without an assertion showed sign-in denial and no records. |
| Operations | Real loopback mTLS permits only the expected certificate identity and fixed request schema; stalled TLS/header clients cannot block the accepting thread. Real PostgreSQL bootstrap tests verify separate runtime/migrator/read-only-backup privileges and no password disclosure on success or failure. |
| Release | Fake loopback GitHub API exercises independent approval, commit/tag/CI/artifact/target binding, current receipts, replay denial and image identity. The collector consumes the verified active release and exact provider/migration receipt hashes before selecting that image. No deployment or registry publication was triggered. |
| Routing and registration | Generated eight Codex adapters, routing fixtures, Nx project registration, Rust target guard and workflow regressions. Buycycle browser checks are a required frontend CI step; the native ARM64 image check feeds the aggregate `ci` gate. |

## Exact image evidence

`buycycle-backend:container-test` builds once for Linux ARM64, runs that image
with isolated PostgreSQL and a synthetic signed-identity service, and retains
`image.tar` plus `evidence.json` outside the checkout. Tests cover production
assets, missing/forged/expired/wrong-audience/unapproved identity, both categories,
state persistence, identity fencing, revision conflict, validation and idempotent
browser import. Running image and canonical OCI config identities are checked.

The evidence names the exact commit, architecture, Docker image ID, config
digest, archive SHA256, test results and whether the source was dirty. The PR
records the final local clean-commit result; CI retains the tested PR archive.
PR merge-commit archives are not eligible for main-release promotion. Only a
successful main-push CI archive can enter the separately approved publication
path, which loads/retests it and never rebuilds source.

## Evidence locations and limits

The local review session retained private fixture evidence outside Git:

- `/private/tmp/buycycle-cross-language-rehearsal.json`
- `/private/tmp/buycycle-restore-rehearsal.json`
- `/private/tmp/buycycle-controlled-grant-rehearsal.json`
- `/private/tmp/buycycle-encrypted-backup-rehearsal.json`

Screenshots show synthetic integrated insights, validation and direct-origin
denial. Temporary local paths are reviewer-session evidence, not durable hosted
artifacts or production receipts. CI and the PR check results provide the
reproducible source gates.

Browser fixtures test UI failures/races; they do not replace the separate real
API/PG walkthrough. Automated axe and keyboard checks are useful accessibility
evidence; a complete manual screen-reader/WCAG audit is not claimed. Attempting
to open the system screen reader through computer control timed out, so that
check is recorded as unavailable, not passed. The image
probes test the proposed resource caps with small synthetic data, not measured
production capacity. Encrypted local recovery does not prove off-device custody,
production recovery targets or zero-loss WAL/PITR.

Actual owner-only Cloudflare OTP/tunnel/DNS, Pi grants/secrets, all old-writer and
source-deploy fences, installed timers/notifications, production reconciliation,
off-device recovery and the separate GitHub requester/managed agent remain
explicit release gates in [Ops readiness](ops-readiness.md). Missing observations
must fail preflight; none may be replaced with a compliance tick.
