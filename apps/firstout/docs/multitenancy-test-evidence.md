# HOLD → safe staging fix round — 2026-11-06

Code snapshot: `8101528` (plus dependency fix `dcc72f1`). Model: gpt-6-astra throughout. Existing branch `feat/firstout-multitenancy-clerk-rls`, PR #905. Synthetic local data only. No merge, deployment, Railway/Clerk/DNS/production/network changes. **Local staging-code verification passed. HOLD remains for production rollout.**

| Check | Final result |
|---|---|
| Complete regular Firstout regression suite, fresh disposable DB | 703 passed, 0 failed, 0 skipped; 417.11 seconds |
| Alembic-migrated non-owner enforced HTTP/database matrix | 13 passed, 0 skipped; 20.02 seconds |
| Frontend unit suite | 101 passed |
| Frontend lint | Passed; 0 errors, 8 pre-existing warnings |
| Frontend typecheck / production build | Passed |
| `npm audit --omit=dev --audit-level=high` | Exit 0; 0 high/critical; 4 low + 60 moderate remain |
| Backend Ruff lint / format | Passed; 544 files formatted |
| Nx project registration / diff whitespace | Passed |
| Live Chromium through unsigned Next proxy | 4 checks passed: legacy login/session, spoof overwrite, invalid bearer rejects despite valid cookie, separate trade login |
| Live production-build Next → API HMAC | 3 checks passed: matching secrets 200, missing signature 400, forged signature 400 |

Exact primary test commands, from repo root (local disposable `FIRSTOUT_TEST_DATABASE_URL` supplied to pytest; never production):

```bash
apps/firstout/backend/.venv/bin/python -m pytest apps/firstout/backend/tests -q --ignore=apps/firstout/backend/tests/test_tenant_database.py
apps/firstout/backend/.venv/bin/python -m pytest apps/firstout/backend/tests/test_tenant_database.py -q
npm run test -w firstout-frontend
npm run lint -w firstout-frontend
npm run typecheck -w firstout-frontend
npm run build -w firstout-frontend
npm audit --omit=dev --audit-level=high
ruff check apps/firstout/backend
ruff format --check apps/firstout/backend
bash .github/scripts/check-nx-projects.sh
git diff --check
```

The ordinary regression suite still uses the existing `create_all` fixture. The separate 13-test matrix creates its own disposable database, migrates through Alembic head, and uses an actual LOGIN NOSUPERUSER NOBYPASSRLS non-owner runtime role. It verifies two-tenant HTTP users/media/public API isolation, inverse trade missing-claim rejection, unknown Clerk subject with existing email, both user/membership default-location tenant FKs, real lifespan in both modes, missing/forged HMAC rejection, canonical-policy checks, partial-grant rejection, activation refusal for superuser, rollback refusal after an additional tenant, pool/abort/commit/refresh behavior, and independent Marrow user scope. All ordinary tests are accounted for by the two primary pytest commands; no security test was skipped.

Default `single_home` boots with the current superuser/no-secret shape and explicitly logs that database tenant isolation is not enforced. Unreleased 081 prepares policies only; routine preDeploy never enables FORCE RLS. A separate operator cutover checks role, policies and grants before transactional activation. Enforced startup validates the restricted role, exact policies, FORCE RLS and proxy secret. No existing enforced database silently falls back to compatibility mode. Directory CRUD requires context; exact-key pre-authentication lookups preserve legacy login. Routine identity reads defer password hashes, while the runtime still needs hash-read access for legacy password verification.

The actual browser checks used local HTTP with secure-cookie mode disabled; the migrated lifespan test separately proves `COOKIE_SECURE=true` with production hostnames and the superuser/no-secret shape. The signed browser smoke used the production build via `npm run start` (Next emitted its standalone launch warning but served all checks); it does not claim a deployed-image rehearsal. Clerk tests use synthetic verification/providers, not real staff or hosted Clerk sign-in. No production backup was read or restored in this round. Existing restricted backup directory remains mode 0700.

A stale initial regression run was interrupted after a mock-context mismatch was corrected. A later reused-database run hit a committed document-number sequence left by that interrupted run. Neither is presented as passing. The next fresh run exposed one two-tenant refund test still using the new single_home default (702 passed, 1 failed). The test now explicitly selects enforced mode; the complete refund module passed 10 tests. The final fresh-database run includes that test-only correction and eliminates fixture contamination without changing application numbering behavior. Logs are retained. The dependency patch is only the follow-redirects override and three lockfile fields; no unrelated dependency upgrade or root uv.lock change.

RLS with mutable `app.tenant_id` protects application mistakes under the restricted role. It does not protect compromised DB credentials/arbitrary SQL, superusers, BYPASSRLS roles or owners. Identity-directory tables remain application-scoped.

Remaining production gates: approved backup access and restored-production rehearsal; staff inventory/cookie/grant comparison; separately provisioned and verified migration/runtime connections and pool topology; coordinated proxy-secret provisioning and explicit stopped-traffic cutover; Clerk plan/import/secrets, wildcard TLS and real staff sign-ins before enabling those capabilities; green remote CI and explicit Engineering/CoS rollout approval. Billing remains off/test-only.

Detailed proof: `astra-fix-regular-suite-final.log`, `fix-round/qa-migrated-matrix.md`, `fix-round/rls-http-pytest.txt`, `fix-round-frontend-*.log`, `fix-round-npm-audit.log`, `fix-round-browser-results.json`, `fix-round-signed-proxy-results.json`, and `fix-round-legacy-login.png` under `/workspace/firstout-multitenancy/proof/`. Earlier evidence below is historical and is superseded by this fix-round result for the changed behavior.

---

## Historical pre-fix evidence

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
