# Firstout multi-tenancy deployment gates

Merging `main` deploys production. The 2026-11-08 release is authorized to activate
Clerk, explicitly link existing staff, and enable public free self-service after
the verification gates below pass. This authorization does not waive failed CI,
restore, isolation, or access checks. Billing stays disabled; no paid upgrade is
authorized. Current operational proof and remaining gates are recorded in
[the release evidence](multitenancy-release-evidence-20261108.md).

## Inventory and backup before any production migration

1. Freeze schema changes and identify the Firstout database, never Marrow. Record the current application SHA and Alembic revision. Confirm exactly one bootstrap team before backfill. Extra teams require an explicit data ownership mapping; do not guess.
2. Run the staff inventory utility against the existing revision in a controlled operator session. Keep its JSON in restricted evidence storage: UUID, email, display name, role slug, sorted exact permissions, disabled state, token version, default location, home team UUID and name. **No hashes, tokens, credentials or connection strings in evidence.** Include custom roles and disabled identities; distinguish the storefront system actor.
3. Capture `pg_dump --format=custom` inside the existing Firstout hosting boundary. Stream it directly into encryption; use a dedicated directory outside `PGDATA`, mode 0700, with archive and encryption material mode 0600. Do not export the production payload to a workstation or add a public TCP proxy. Record SHA-256, time, location and retention owner, never commit the archive or key.
4. Decrypt and restore using `pg_restore --exit-on-error --no-owner --no-privileges` into a named disposable database inside that same boundary. Verify the selected target before running it. Disable outbound mail, WhatsApp, storage writes, LLM calls and scheduled reminders. Compare every table's row count and exact staff state inside the database, outputting aggregate results only. Verify a synthetic account login, representative reads and pre-change cookie compatibility through the restored database. Record commands, exit codes and checks without credentials. An untested dump does not pass this gate.
5. Rehearse upgrade, downgrade and reapply on that disposable restore. Compare staff inventory before/after: identical identity UUID, password digest (compare inside DB without exporting), token version and disabled state; every inventoried grant remains on the original membership. Test existing cookies. Do not deploy if any access path is removed.

## Explicit stages: compatibility first, enforcement by operator cutover

`TENANT_ISOLATION_MODE=single_home` is the default. It boots against the current
production `postgres` URL, with no Clerk configuration and no proxy secret. It
logs that **database tenant isolation is NOT enforced**. Startup refuses a second
team, any home slug other than `firstout`, enabled Clerk/import/signup, or any
already-active tenant RLS. Request authentication also rejects other teams.
This stage serves only the existing home and preserves `firstout_session` login,
existing cookies, forgot-password and staff access. It is not a multi-tenant mode.
`COOKIE_SECURE` controls cookies only and never selects the database security mode.

Without `FRONTEND_PROXY_SECRET`, the API ignores `x-firstout-frontend-host` and
validates the direct API/apex host. That untrusted header never selects a tenant;
direct tenant hosts are unavailable in single-home mode. With a secret configured,
Next strips supplied forwarding/signature headers and sends HMAC-SHA256 of the
normalized frontend host as `x-firstout-proxy-signature`; the API requires the
matching signature. Configure the same server-only secret on both services during
an approved coordinated change and test before enforcement. A one-sided secret
change can fail proxy requests; it is not an approved intermediate serving state.
The signature authenticates a host assertion, not user identity or arbitrary
request content. Membership checks remain required.

### Routine preDeploy: schema preparation, no RLS activation

Railway retains `DATABASE_URL="${MIGRATION_DATABASE_URL:-$DATABASE_URL}" alembic
upgrade head`. Revisions 079 and 080 preserve home identity/grants and backfill
business `team_id`, scoped keys and composite tenant foreign keys. This is a real
schema/data migration: the inventory and restored-backup rehearsal above remain
required before authorizing deployment. Revision 080 changes **row ownership
columns**, not PostgreSQL table owners or role credentials.

**081 installs the policies only; it does not ENABLE or FORCE RLS.** These revisions
are unreleased on the verified production shape. They are deliberately corrected
before release. No environment-conditioned no-op is stamped as an applied security
migration. `alembic upgrade head` does not activate or deactivate existing RLS,
including on subsequent deploys. A database already running the earlier PR's 081
with FORCE RLS must use enforced mode or the explicit single-home rollback below;
startup never silently disables its protection.

### Separately authorized cutover (never part of preDeploy)

1. Complete the backup restore, staff cookie/login, permission comparison and
   Alembic upgrade/reversal rehearsal on a disposable production restore. Save
   aggregate evidence without credentials. Use authenticated private service SSH;
   do not open a public database TCP proxy for this operation.
2. Provision a dedicated runtime role `NOSUPERUSER NOBYPASSRLS`, owning no
   application table, with no membership in owner/superuser/BYPASSRLS roles.
   Grant schema usage and only required application DML/sequence privileges.
   Keep `MIGRATION_DATABASE_URL` restricted to the operator/preDeploy owner
   connection. Never switch the serving runtime credential yet.
3. Rehearse both database URLs on the exact intended topology. The command
   compares database name and server address/port, but this is not a substitute
   for verifying endpoint identity (especially Unix sockets or poolers). Ensure
   the role has every required SELECT/INSERT/UPDATE/DELETE grant. Identity tables
   remain application-scoped; a shared legacy-login runtime still needs password
   verification access. Do not describe their broad DB grants as RLS isolation.
4. Provision and verify the matching proxy secret, keep Clerk/signup/import off,
   and prepare `TENANT_ISOLATION_MODE=enforced` plus the new runtime URL. Stop
   serving traffic and pause workers for the short cutover boundary. Do not run
   the compatibility API concurrently with activation: its owner credential
   would bypass RLS and must not serve multi-tenant traffic.
5. In a controlled operator environment (URLs in secret environment, never argv),
   with the prepared **runtime** `DATABASE_URL`, explicit owner
   `MIGRATION_DATABASE_URL`, `TENANT_ISOLATION_MODE=enforced`, and proxy secret:

   ```bash
   cd apps/firstout/backend
   uv run python -m app.commands.tenant_cutover activate
   ```

   The command checks the actual runtime role, table-owner membership, canonical
   prepared policies, same DB and all DML grants before transactional ENABLE/FORCE.
   It commits activation and verifies it through the runtime connection. A failure
   before commit rolls back activation. A verification/connection failure after
   commit leaves RLS active: inspect it; never assume rollback occurred.
6. Switch the stopped API to the verified runtime URL and enforced mode, then
   restart. Startup requires a proxy secret, non-owner/non-bypass runtime role,
   exactly the canonical tenant policies, and ENABLE + FORCE on every business
   table. It refuses to boot on mismatch even with `COOKIE_SECURE=false`.
   Repeat actual legacy staff login/cookie, two-tenant HTTP, asset and job checks
   before restoring traffic or creating a second tenant. Enabling Clerk and new
   tenant provisioning remains a later independently approved gate.

### Threat model

RLS with mutable `app.tenant_id` protects against application mistakes such as
missing tenant filters and foreign-UUID access when the runtime is a non-owner
`NOBYPASSRLS` role. Composite foreign keys prevent cross-tenant references.
The application selects the GUC after authenticating membership; transactions and
pool cleanup prevent context leakage. This does **not** protect compromised DB
credentials capable of setting another tenant GUC, arbitrary SQL execution,
superusers, BYPASSRLS roles, or owners able to alter policies. There is no claim of
SQL-injection immunity. Directory identities/memberships are application-scoped,
with narrow pre-authentication lookup paths; they are not covered by business RLS.

## Clerk dual-auth rollout

Confirm Organisations, membership-required sessions, and required token claims are available on the already authorized Clerk plan. If an additional paid feature is required, stop and record `RISK.md`; do not upgrade. Use standard org roles plus Firstout's local permission catalogue rather than purchasing custom roles. Disable frontend organisation creation for imported members; never enable Clerk Billing.

Configure the issuer/JWKS, authorized parties, publishable key and Svix signing secret through secret storage. Keep secrets out of source, browser bundles (except the publishable key), test evidence and logs. After enforcement cutover, retain the same server-only `FRONTEND_PROXY_SECRET` on frontend and API. Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` at frontend build time; the Dockerfile exposes this public argument explicitly. The Next.js server and API both require runtime `CLERK_SECRET_KEY`. The frontend may reference `${{firstout-api.CLERK_SECRET_KEY}}`; never add that secret as a Docker build argument or Next public environment variable. `FIRSTOUT_ALLOW_LOCAL_HOSTS=true` is only for local production-shaped smoke tests. The proxy overwrites browser-provided forwarding headers and the API validates the strict host before comparing it with signed membership. Keep legacy login and forgot-password available.

Use `https://app.firstout.co.za` as the canonical self-service host. Leave
`NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED=false` unless wildcard DNS and TLS are
verified. Signed active-organisation sessions work on the canonical host without
wildcard routing. Configure the webhook at
`https://api.firstout.co.za/api/v1/webhooks/clerk`, subscribing to
`organizationMembership.created`, `organizationMembership.updated` and
`organizationMembership.deleted`. Stage its signing secret before enabling
`CLERK_WEBHOOK_RECONCILE_ENABLED`; signed events remain quarantined while that
flag is false. Webhook reconciliation checks current provider membership and
never disables an imported legacy home membership.

At activation, enable public verified-email signup in Clerk while keeping
frontend organisation creation disabled: Firstout's onboarding API provisions
the organisation, owner membership, settings and first location. New organisations
have five staff places. The existing home organisation retains all seven human
staff with a per-organisation cap of seven, within Clerk's documented free
maximum of twenty; do not silently omit staff or purchase an upgrade.

Rehearse import only with synthetic users and a fake provider or a confirmed Clerk test instance. Import bcrypt digest with external_id equal to Firstout UUID. Never link by email string, never reset passwords as an import strategy, never import the storefront system actor. Disabled users must be locked before completing the import. Failed imports leave local login and grants intact. Preserve local home memberships when Clerk deletion webhooks arrive. A roster is not login proof.

After a separately approved production import, record real sign-in evidence for the existing owner and every distinct live role (including custom roles): person, Europe/Luxembourg timestamp, tenant, and legacy/imported-password/verified-factor path. Staff perform their own sign-ins. Do not record passwords or tokens. Engineering verifies host mismatch rejection and tenant switching. **Do not retire legacy cookie issuance before this gate; keep accepting unexpired cookies afterward.**

## Railway Pro wildcard DNS and TLS (operator instructions only)

Keep `firstout.co.za` and `www.firstout.co.za`. Add `app.firstout.co.za` and `*.app.firstout.co.za` to Firstout's frontend service in its own Railway project. Keep `api.firstout.co.za` on the API service; do not add `*.firstout.co.za` across services. Copy the exact CNAME, `_acme-challenge` CNAME and TXT values Railway supplies; do not invent targets. Use DNS-only for the nested wildcard and challenge records so Railway serves its certificate without a Cloudflare paid certificate add-on. Verify parent and wildcard TLS, an unused test slug (404), known tenant slug, and API routing. Restrict Clerk redirect origins to the approved hosts and scope staff cookies to `.app.firstout.co.za`.

## Branding, jobs and billing

New storage references use `tenants/{team_id}/…`. Retain existing references until a separately audited object-copy migration verifies content and updates owning rows; never delete old objects before validation. Back up the object inventory alongside the database. Test tenant-specific branding, label dimensions/fields, Cin7 concurrent locks and reminders. WhatsApp status callbacks require a unique configured phone-number mapping and verified signature. Trade portal stays on its own customer cookie, outside Clerk Organisations.

Billing remains disabled and provider test mode only. Public free organisation
signup is enabled only after enforced isolation and the Clerk integration gates
pass. No live Stripe/Paystack products or charges are created.

## Rollback

Stop the rollout on any lost legacy login/grant, cross-tenant read/write, missing asset, invalid runtime role, or unexplained migration difference. Disable new Clerk/signup entry points while retaining legacy login; pause background jobs. Do not delete imported users, memberships, hashes or token versions. Revert application deployment to the recorded compatible SHA only after checking schema compatibility.

Before any additional tenant exists, an approved rollback can stop traffic/jobs,
set the operator environment to `TENANT_ISOLATION_MODE=single_home` with all
Clerk/signup/import flags false, and run
`uv run python -m app.commands.tenant_cutover deactivate` using the owner URL.
This refuses unless only the original Firstout team exists, transactionally
removes ENABLE/FORCE while retaining prepared policies, and checks compatibility.
Then restore the compatibility runtime settings and verify staff access before
resuming traffic. Rehearse activate → deactivate → activate on a disposable DB.
Do not downgrade schema just to roll back enforcement. Once any additional tenant
exists, this compatibility rollback is forbidden: keep enforced mode, repair or
restore to an isolated replacement. Disabling RLS is never a production workaround
for a tenant leak. For a destructive migration failure, halt writes, restore the tested encrypted backup into a replacement isolated instance, validate inventory, documents and sign-ins, then perform a separately approved connection cutover. Retain the failed database for investigation. Down-migrating scoped uniqueness can fail once tenants share natural keys; never delete conflicting rows to force downgrade. Restore is the recovery path in that case.

## Evidence checklist

Keep current local results in [test evidence](multitenancy-test-evidence.md) and
operational results in [release evidence](multitenancy-release-evidence-20261108.md).
Historical synthetic artifacts do not establish production readiness. Required
release evidence includes a restored production backup rehearsal, exact staff
permission preservation, actual runtime-role topology, confirmed plan capability,
Clerk hosted integration, green CI, and live post-deploy smoke. Real staff perform
their own sign-ins; keep legacy login available until those access checks pass.
