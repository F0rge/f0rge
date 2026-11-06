# Firstout multi-tenancy deployment gates

This PR stage authorizes local synthetic tests and a PR into `main` only. **Do not merge or deploy without Engineering gates and Chief of Staff (CoS) approval.** Merging `main` deploys production. No live database, Clerk import, DNS, Railway setting, billing product or payment is changed by the implementation run.

## Inventory and backup before any production migration

1. Freeze schema changes and identify the Firstout database, never Marrow. Record the current application SHA and Alembic revision. Confirm exactly one bootstrap team before backfill. Extra teams require an explicit data ownership mapping; do not guess.
2. Run the staff inventory utility against the existing revision in a controlled operator session. Keep its JSON in restricted evidence storage: UUID, email, display name, role slug, sorted exact permissions, disabled state, token version, default location, home team UUID and name. **No hashes, tokens, credentials or connection strings in evidence.** Include custom roles and disabled identities; distinguish the storefront system actor.
3. Set `PGSERVICE=firstout-backup` using a restricted local service/password file. Run `pg_dump --format=custom --file=firstout-before-mt.dump`. Encrypt and restrict the dump: it contains sensitive identity and business data. Record SHA-256, time and retention owner, never commit it.
4. Restore onto a disposable isolated instance using a separate `PGSERVICE=firstout-restore` and `pg_restore --exit-on-error --no-owner --dbname=firstout_restore firstout-before-mt.dump`. Ensure this service points only at the disposable instance. Start the pre-change API against the restore with outbound mail, WhatsApp, storage writes and scheduled reminders disabled. Verify a synthetic account login, representative document reads, and totals/counts. Record commands, exit codes and checks without credentials. An untested dump does not pass this gate.
5. Rehearse upgrade, downgrade and reapply on that disposable restore. Compare staff inventory before/after: identical identity UUID, password digest (compare inside DB without exporting), token version and disabled state; every inventoried grant remains on the original membership. Test existing cookies. Do not deploy if any access path is removed.

## Runtime roles and isolation

Use separate migration and runtime connections. The runtime role must be `NOSUPERUSER NOBYPASSRLS`, must not own any application table, and must not inherit the migration owner role. Grant only schema usage and application DML/sequence access. Verify `pg_roles` and `pg_class` ownership using an operator connection; never print connection URLs. Test using the actual runtime connection topology, including any transaction pooler and configured direct connection selection.

Apply schema and backfill revisions after `078_password_reset`, then enable the separately reversible FORCE RLS revision only after the synthetic non-owner isolation matrix passes. Cross-tenant migration data work uses `f0rge_db.rls.migration_bypass`; runtime code must never set the migrator service role. Confirm policies on every tenant-owned table, composite tenant foreign keys, scoped uniqueness, and no-context raw SQL denial. Exercise commit/refresh, failed transaction rollback and pool reuse. Every request and detached job must use the tenant session helper, including CLI import with explicit `--team-id`.

## Clerk dual-auth rollout

Confirm Organisations, membership-required sessions, and required token claims are available on the already authorized Clerk plan. If an additional paid feature is required, stop and record `RISK.md`; do not upgrade. Use standard org roles plus Firstout's local permission catalogue rather than purchasing custom roles. Disable frontend organisation creation for imported members; never enable Clerk Billing.

Configure the issuer/JWKS, authorized parties, publishable key and Svix signing secret through secret storage. Keep secrets out of source, browser bundles (except the publishable key), test evidence and logs. Set the same server-only `FRONTEND_PROXY_SECRET` on frontend and API before enabling the new proxy. Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` at frontend build time and `CLERK_SECRET_KEY` server-side when enabling Clerk. `FIRSTOUT_ALLOW_LOCAL_HOSTS=true` is only for local production-shaped smoke tests. The proxy overwrites browser-provided forwarding headers and the API validates the strict host before comparing it with signed membership. Keep legacy login and forgot-password available.

Rehearse import only with synthetic users and a fake provider or a confirmed Clerk test instance. Import bcrypt digest with external_id equal to Firstout UUID. Never link by email string, never reset passwords as an import strategy, never import the storefront system actor. Disabled users must be locked before completing the import. Failed imports leave local login and grants intact. Preserve local home memberships when Clerk deletion webhooks arrive. A roster is not login proof.

After a separately approved production import, record real sign-in evidence for the existing owner and every distinct live role (including custom roles): person, Europe/Luxembourg timestamp, tenant, and legacy/imported-password/verified-factor path. Staff perform their own sign-ins. Do not record passwords or tokens. Engineering verifies host mismatch rejection and tenant switching. **Do not retire legacy cookie issuance before this gate; keep accepting unexpired cookies afterward.**

## Railway Pro wildcard DNS and TLS (operator instructions only)

Keep `firstout.co.za` and `www.firstout.co.za`. Add `app.firstout.co.za` and `*.app.firstout.co.za` to Firstout's frontend service in its own Railway project. Keep `api.firstout.co.za` on the API service; do not add `*.firstout.co.za` across services. Copy the exact CNAME, `_acme-challenge` CNAME and TXT values Railway supplies; do not invent targets. Use DNS-only for the nested wildcard and challenge records so Railway serves its certificate without a Cloudflare paid certificate add-on. Verify parent and wildcard TLS, an unused test slug (404), known tenant slug, and API routing. Restrict Clerk redirect origins to the approved hosts and scope staff cookies to `.app.firstout.co.za`.

## Branding, jobs and billing

New storage references use `tenants/{team_id}/…`. Retain existing references until a separately audited object-copy migration verifies content and updates owning rows; never delete old objects before validation. Back up the object inventory alongside the database. Test tenant-specific branding, label dimensions/fields, Cin7 concurrent locks and reminders. WhatsApp status callbacks require a unique configured phone-number mapping and verified signature. Trade portal stays on its own customer cookie, outside Clerk Organisations.

Billing remains disabled and provider test mode only. Signup is a gated scaffold until provisioning and merchant choice are separately approved. No live Stripe/Paystack products or charges.

## Rollback

Stop the rollout on any lost legacy login/grant, cross-tenant read/write, missing asset, invalid runtime role, or unexplained migration difference. Disable new Clerk/signup entry points while retaining legacy login; pause background jobs. Do not delete imported users, memberships, hashes or token versions. Revert application deployment to the recorded compatible SHA only after checking schema compatibility.

The RLS revision can be downgraded separately during isolated rehearsal, but disabling RLS is not a safe production workaround for a tenant leak. For a destructive migration failure, halt writes, restore the tested encrypted backup into a replacement isolated instance, validate inventory, documents and sign-ins, then perform a separately approved connection cutover. Retain the failed database for investigation. Down-migrating scoped uniqueness can fail once tenants share natural keys; never delete conflicting rows to force downgrade. Restore is the recovery path in that case.

## Evidence checklist

Local results: `/workspace/firstout-multitenancy/proof/TEST-RESULTS.md`, `test-summary.json`, browser notes/screenshots and `PR.json`. These synthetic artifacts do not establish production readiness. Required later evidence: restored production backup rehearsal, real staff permission inventory comparison, actual runtime-role/pool topology tests, paid-plan confirmation, wildcard TLS, and real staff sign-ins. Engineering and CoS must approve those gates before merge/deploy.
