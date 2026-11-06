# Firstout multi-tenancy — local QA evidence

Branch: `feat/firstout-multitenancy-clerk-rls`. Model: gpt-6-astra throughout. Synthetic data only. No production changes, merge or deployment.

| Check | Result |
|---|---|
| Full Firstout backend regression | 674 passed, 0 failed, 5 skipped; 467.55 seconds |
| Final isolated non-owner database matrix | 6 passed, 0 skipped; 17.18 seconds |
| Clerk authenticated remote media | 2 passed; existing SKU regression suite 24 passed |
| Shared DB / shared test helpers | 15 / 4 passed |
| Frontend unit tests | 101 passed |
| Frontend lint / typecheck / production build | Passed (existing image lint warnings only) |
| Nx affected frontend | lint, typecheck, test, build passed |
| Nx affected Python | 18 lint/format targets across 9 projects passed |
| Ruff check / format / diff whitespace | Passed |
| Live local Chromium | Legacy login, signed synthetic Clerk bearer, forged JWT rejection, host mismatch, spoof overwrite, label save and trade login passed |
| Synthetic backup/restore | Dump/restore exited 0; inventory matched; restored app startup, legacy login and settings reads passed |

The full suite collected the earlier environment-gated security tests, hence five skips. The final security fixture now automatically creates a separate disposable database using the testcontainers fixture (or explicitly opted-in native local test DB). Its separate six-test run passed without skips. Explicit overrides are restricted to guarded local test database names.

The security matrix uses an actual LOGIN NOSUPERUSER NOBYPASSRLS role that does not own application tables. It covers tenant SELECT/INSERT/UPDATE/DELETE, duplicate SKU references/barcodes/invoice numbers, authenticated foreign UUID 404, composite-FK rejection, same-connection pool reuse, abort/rollback, commit/refresh, independent Cin7 locks, explicit detached-job context, reminder/label settings, branding/import storage, and existing Marrow app.user_id isolation. It also upgrades, downgrades to 078 and reapplies migrations while comparing synthetic staff hashes, token versions and grants in memory; hashes are not exported.

The browser Clerk path uses a fake JWKS key with real RS256 verification. It does not prove hosted Clerk UI or real staff login. The backup/restore uses only synthetic data, not a production dump. The full Marrow application suite was not run locally because its Docker/pgvector fixture is unavailable; shared tests and a real non-owner Marrow RLS check passed.

Detailed artifacts in `/workspace/firstout-multitenancy/proof/`: `auth-results.{md,json}`, `database-results.{md,json}`, `nx-python-results.{md,json}`, `frontend-results.json`, `BROWSER-WALKTHROUGH.md`, `browser-results.json`, `browser-clerk-results.json`, screenshots, `RESTORE-REHEARSAL.md`, and `restore-results.json`. Machine-readable aggregate: `test-summary.json`. PR identity: `PR.json` after opening.

Reproduction: set an explicit disposable `FIRSTOUT_TEST_DATABASE_URL` (local firstout_* database), then `uv run --project apps/firstout/backend pytest apps/firstout/backend/tests -q`. Without that override, the standard testcontainers fixture runs. The RLS test module provisions its own separate database; an explicit `FIRSTOUT_RLS_TEST_DATABASE_URL` is only accepted for the guarded local proof database. Use Nx affected targets with base f155a2b and the feature head. Never point these commands at production.

Deployment remains blocked pending Engineering and CoS approval of the runbook: tested production restore, staff inventory comparison, actual runtime-role/pool checks, Clerk plan/configuration/secrets and import transport, wildcard DNS/TLS, and real staff sign-in evidence. Billing remains disabled/test-only; signed webhooks quarantine changes rather than stripping local access.
