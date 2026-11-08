# Development

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-040

- **Policy status:** Accepted
- **Temporary ID:** P-040
- **Category:** Development
- **Decision:** One standard command starts the full app locally with database and safe seed data.
- **Proposed enforcement (not installed):** Proposed platform dev entrypoint per app; clean-checkout CI smoke starts full stack, waits for readiness and verifies idempotent safe seeding.
- **Gate and limit:** Integration: startup/seed smoke evidence with no manual secret setup for fake/sandbox mode. Exact command chosen after repo assessment.
- **Static evidence at `f155a2ba` (not normative, not a live check):** No clean-checkout CI job starts every app and checks idempotent seeding.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-041

- **Policy status:** Accepted
- **Temporary ID:** P-041
- **Category:** Development
- **Decision:** Agents build/test the entire app locally; CI runs automated tests. No hosted preview/staging environment is required.
- **Proposed enforcement (not installed):** Documented local harness and reproducible CI jobs; capture commands, commit, results and browser evidence. Release uses the same tested build.
- **Gate and limit:** Test + review: honest run reports, not agent claims alone. This policy does not authorize production testing or remove release approval.
- **Static evidence at `f155a2ba` (not normative, not a live check):** nx affected lint, format, test, typecheck, build, codegen, and storybook targets, plus a separate e2e workflow. Historical push runs on main succeeded through 2026-10-29. Those runs were not performed here.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-042

- **Policy status:** Accepted
- **Temporary ID:** P-042
- **Category:** Development
- **Decision:** Local/CI external services use fakes or sandboxes: no real emails, charges, paid-service side effects or production writes.
- **Proposed enforcement (not installed):** Default-deny outbound network in test harness where feasible; fake adapters/sandbox allowlist, non-prod credentials and tests that reject production service configuration.
- **Gate and limit:** Integration + runtime: blocked-side-effect canaries and configuration report. Mocking one SDK is not sufficient if alternate egress remains.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Testcontainers for some suites. npm audit and pip-audit. No canary that fails when a test is pointed at a production host.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** high.
- **Approved exception:** None.

## P-043

- **Policy status:** Accepted
- **Temporary ID:** P-043
- **Category:** Development
- **Decision:** Test against the actual chosen database engine, not a convenient substitute.
- **Proposed enforcement (not installed):** Disposable PostgreSQL integration environment applies migrations and exercises concurrency, constraints and transactions; legacy exceptions use their actual engine until migrated.
- **Gate and limit:** Integration: DB version and transaction test evidence. SQLite-only success cannot establish PostgreSQL correctness.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Pytest plus testcontainers where those fixtures are used. Not a platform rule that fails a Postgres app whose tests only use SQLite.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-044

- **Policy status:** Accepted
- **Temporary ID:** P-044
- **Category:** Development
- **Decision:** Shared dependency upgrades are reviewed and tested against affected apps; no silent production upgrades.
- **Proposed enforcement (not installed):** Lockfiles, reverse-dependency impact matrix and reviewed upgrade PRs; shared policy changes trigger wider regression tests. Assess Dependabot/Renovate later.
- **Gate and limit:** Static + tests + release: lockfile diff and affected-app results. Update bot not selected; bot PR does not grant production release approval.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Lockfiles, Dependabot for three directories, npm audit on CI, marrow pip-audit when that project is affected, and nx affected tests.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

