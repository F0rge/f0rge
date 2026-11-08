# Firstout multi-tenancy — implementation brief

For Codex Astra 6 (implement) and Engineering (test, then deploy to `main`). This file is a handoff, not a second design. Follow `/workspace/firstout-multitenancy/design.html` as the source of truth.

This document pass did **not** change the repo, Railway, Cloudflare, Clerk production config, or any live user.

## Mandate

Leo, Friday 6 November 2026, 17:45 Europe/Luxembourg (UTC+1), verified in the Chief of Staff transcript:

> Ive added pro sub. Add both to design. Then have codex astra 6 implement the design and you test it and then deploy to main. Do not remove any users current access.

“Both” means **Clerk auth + Clerk Organisations** and the **Railway Pro wildcard** (`app.firstout.co.za` plus `*.app.firstout.co.za`). Not Cloudflare Access.

Hard constraint: **do not remove any user’s current access.**

Firstout conventions: PRs target `main` and squash-merge; Python 3.11; no root `uv.lock`; IBM Carbon, not `@f0rge/ui`. Do not print secrets. Do not buy any paid add-on beyond the already-chosen Railway Pro without a fresh yes.

Deploy to `main` only after Engineering tests pass **and** the safety gates below are green. Leo’s deploy instruction does not waive backup, dual-auth, permission preservation, or live sign-in evidence.

## What to build

- Tenant = organisation = existing `teams` row. Locations stay locations.
- Shared Postgres + `team_id` + FORCE RLS. Application filters stay. Policies use `app.tenant_id`, not `app.user_id`.
- Clerk for staff login, Organisations, memberships, `OrganizationSwitcher` (`hidePersonal`), and signed session claims (`orgId` / `orgSlug` mapped to local `teams.clerk_org_id`). FastAPI verifies Clerk JWTs via JWKS.
- Firstout `has_permission` and the existing permission catalogue stay authoritative. Map Clerk org roles onto presets; never drop inventoried grants to fit a coarser Clerk default. Do not turn on Clerk Billing (it can gate permissions).
- Dual-auth trickle migration: accept `firstout_session` **or** a Clerk session until cutover criteria are met.
- Wildcard hosts on Railway Pro: keep `firstout.co.za` and `www.firstout.co.za`; add `app.firstout.co.za` (Clerk primary; wildcard does not cover the parent name) and `*.app.firstout.co.za` on `firstout-frontend`. Leave `api.firstout.co.za` on `firstout-api` (Railway overlap rule: do not use `*.firstout.co.za`).
- Host resolution: trusted forwarded-host configuration; validate exact suffix `{slug}.app.firstout.co.za` (or the listed apex/app hosts) and a strict slug. Next must overwrite any client-supplied forwarded host and send a validated `X-Firstout-Frontend-Host` (or equivalent) because the `/api` rewrite otherwise presents `Host: api.firstout.co.za`. **Host is never authorisation.** It must match the signed Clerk org membership (or, for a legacy cookie, the user’s inventoried home team). Mismatch fails closed.
- Billing scaffold only, behind a flag and provider test mode. No live products or payments until the merchant of record is chosen (Stripe vs Paystack still open).
- Trade portal (`firstout_customer_session`) stays out of Clerk staff Organisations unless a later yes says otherwise.
- Prefer DNS-only (grey cloud) for the nested wildcard so Railway issues the Let’s Encrypt wildcard cert. Do not buy Cloudflare Advanced Certificate Manager or a Clerk plan upgrade without a fresh yes; pause and report if a required Clerk feature is paid and not already available.

## Acceptance criteria

1. Existing active staff can still use Firstout after every migration and deploy. Disabled users stay unable to sign in.
2. A complete pre-change inventory of staff users exists (id, email, display name, role slug, exact permission keys, `is_disabled`, `token_version`, `default_location_id`, `team_id`, team name). No password hashes in that artefact.
3. After backfill, a programmatic comparison shows every inventoried user still has at least those permission keys on their legacy home membership. No silent reduction.
4. Users are imported to Clerk with `external_id` = Firstout user UUID and, where Clerk accepts it, `password_digest` + `password_hasher: "bcrypt"` (Firstout already uses bcrypt / `$2b$`). Import uses backoff for CreateUser rate limits.
5. Linking is only via that hash import or a later Clerk sign-in whose **verified** email matches exactly one unlinked Firstout user. No email-only automatic linking. No forced password resets. No mass “set your password” email as the migration path.
6. Dual-auth: FastAPI accepts a valid `firstout_session` or a valid Clerk session. Existing cookies are not bulk-revoked by the rollout. Unmigrated users keep Firstout email/password and the current forgot-password flow.
7. A Clerk roster, or `clerk_user_id` being set, is **not** proof of login. Production retirement of custom login requires recorded real sign-in evidence for pre-existing active staff: at least the owner and each distinct live role actually in use (till, books, warehouse, buyer, any custom role in use), using their existing password or another verified Clerk factor they completed themselves. Record who, when (Europe/Luxembourg), and which path (legacy cookie / Clerk imported hash / verified-email link). Fixture tests prove the hasher mechanism only.
8. Legacy `firstout_session` binds only to the inventoried home team (`is_legacy_home`). It cannot switch tenant. A different host or spoofed forwarded host does not open another tenant; mismatch is 403/404.
9. Tenant switching happens only with a signed Clerk session whose `org_id` maps to a team the user is a member of (`OrganizationSwitcher` / `getToken()`). Multi-tab safety: API calls send a fresh token from `getToken()`, not a stale singleton cookie.
10. Request path: authenticate first (Clerk JWT or legacy cookie) → map to a team → if a tenant host is present, its validated slug must equal that team’s slug → set tenant context → `has_permission` from Firstout roles.
11. Host parser accepts only `firstout.co.za`, `www.firstout.co.za`, `app.firstout.co.za`, or `{slug}.app.firstout.co.za`. Slug `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$`, full-string suffix check. Reserved slugs as in the design (www, api, app, admin, mail, status, support, billing, signup, login, static, cdn, trade). Spoofed forwarded hosts fail closed and never grant access.
12. Tenant GUC mechanism is chosen only after tests of: write + commit + `refresh()`; connection reused from tenant A to tenant B (no leftover GUC or rows); failed/aborted transaction; the actual URL the API uses (pooled vs direct — do not print it). Do not default to session-scoped settings. If `SET LOCAL` / `set_config(..., true)` plus `after_begin` re-apply passes those tests, prefer it. Session-scoped settings are allowed only if the same tests pass and `RESET` (not empty string) runs on every session factory: request `get_db`, Cin7 `_run_detached`, payment-reminder ticker, CLI import.
13. FORCE RLS is on for tenant-owned tables; the app role is not table owner and does not have `BYPASSRLS`. Raw SQL without a tenant GUC returns no tenant rows. UUID IDOR across tenants is 404. `WITH CHECK` blocks cross-tenant writes. Two tenants may share the same `our_ref` / document number without collision or leakage.
14. Cin7 one-active lock is per team. Detached jobs and the payment-reminder ticker set tenant context themselves. Storage keys move under `tenants/{team_id}/…`.
15. Unique indexes that are global today become `(team_id, …)` as listed in the design (SKUs, barcodes, locations, customers, role slugs, document numbers, account codes, trade-portal emails if globally unique, Cin7 active lock).
16. New Alembic revisions after `078_password_reset`. Do not edit already-applied migration files.
17. Clerk webhooks (`POST /api/v1/webhooks/clerk` or similar) verify Svix signatures. `svix-id` is the idempotency key. During dual-auth, `user.deleted` / `organizationMembership.deleted` must not strip a pre-existing user’s local home membership or delete the Firstout user to “match Clerk.”
18. Organizations enabled; prefer membership required; `createOrganizationEnabled: false` for imported members; new tenants provisioned via Firstout + Clerk Backend API.
19. Wildcard DNS/TLS works for an unused test slug without a per-tenant Railway domain. Unknown slugs 404. `api.firstout.co.za` remains on the API service.
20. Billing code, if added, cannot charge anyone: feature flag off and/or provider test mode, no live products.
21. Trade portal customers still sign in with `firstout_customer_session`.
22. Isolation, host, legacy-session, Clerk-mismatch, permission-snapshot, disabled-user, webhook-forgery, and GUC pool-lifecycle tests all pass.

## Migration and deploy safety gates

Do these in order. A later phase does not start until the earlier gate is done.

1. **Inventory** all staff users and current roles/permissions (see acceptance criterion 2). Confirm unexpected extra teams (expect one, bootstrap name “Firstout”).
2. **Backup** the live Firstout Postgres database. **Restore it onto a disposable instance** and confirm the app can start against the restore. An untested dump is not a rollback plan. Write the rollback steps before migrating.
3. Schema spine: `teams.slug`, `status`, `clerk_org_id`; `users.clerk_user_id`; `memberships` backfilled from `users.team_id` with `is_legacy_home` and unmodified grants. First team slug `firstout` (unless Leo picks another). No login behaviour change in this step.
4. Stamp `team_id` onto tenant-owned tables, backfill from that single team, then NOT NULL + rewritten unique indexes.
5. Clerk import (bcrypt digest + `external_id`) and Organisation/membership create. Failures leave Firstout login intact. Disabled users are locked/banned in Clerk. Do not give the storefront system actor a staff Clerk login.
6. Dual-auth on. Next.js Clerk provider (`@clerk/nextjs`, `ClerkProvider` in `<body>`, `proxy.ts` on Next.js 16) plus FastAPI JWKS verification. Appearance follows Carbon.
7. Add Railway/DNS hosts only at this implementation step (not during the design pass): `app.firstout.co.za` and `*.app.firstout.co.za` on `firstout-frontend`, plus Railway’s wildcard CNAME / `_acme-challenge` CNAME / TXT. Keep `_acme-challenge` DNS-only. Prefer DNS-only for the nested wildcard.
8. Isolation tests + GUC matrix + host/spoof tests + permission snapshot comparison.
9. Enable FORCE RLS only after those tests pass against a non-bypass role. This step must be separately reversible.
10. **Live sign-in evidence** (criterion 7) before stopping issuance of new `firstout_session` cookies. Keep accepting unexpired legacy cookies after that.
11. Billing remains flagged off / test-mode. No live Stripe or Paystack products.
12. Engineering regression test, then squash-merge to `main` and deploy. If anything in gates 1–11 is red, do not deploy.

Rollback: restore the tested backup if a migration or import goes wrong. Down-migrations are extra safety, not a substitute for a tested restore. Cross-tenant SQL inside migrations uses `f0rge_db.rls.migration_bypass`.

## Auth migration rules (short)

| Allowed | Forbidden |
| --- | --- |
| Trickle / dual-auth | Big-bang cutover that ends existing sessions |
| Clerk CreateUser with bcrypt digest + `external_id` | Email-string-only auto-link |
| Link after a verified Clerk identity matches one unlinked user | Forced password reset as the path |
| Keep hashes until custom login is retired | Deleting hashes or users to “clean up” early |
| Map Clerk org roles onto Firstout presets without reducing grants | Replacing `has_permission` with Clerk `has()` for shop actions |
| Ignore or quarantine Clerk delete webhooks during dual-auth so local home access stays | Treating a webhook as licence to strip current access |

## Unknowns (do not invent answers)

- Who invoices tenants (Stripe if billed from a Stripe country such as Luxembourg; Paystack if a South African company bills). Do not go live on either until this is answered.
- Whether the original shop keeps using `https://firstout.co.za` as a legacy host after others get slugs (design recommends yes during dual-auth).
- Preferred first-tenant slug (design recommends `firstout`).
- Year-one tenants SA-only for VAT/VAT201?
- Platform-admin impersonation in v1?
- Invite-only signup until RLS and sign-in evidence land?
- When, if ever, the trade portal moves to Clerk.
- Live Postgres owner / `BYPASSRLS` / pooler topology (not queried in research; verify before FORCE RLS). Do not print connection strings.
- Live Cloudflare records.
- Whether the connected Clerk instance already has Organisations enabled, and whether needed features (custom roles, MRU, session-token customisation) require a paid Clerk plan we do not already have. If yes: pause and ask; do not upgrade.
- Whether every production bcrypt hash is a format Clerk’s `bcrypt` hasher accepts (expected `$2b$` / `$2a$`; confirm at import, leave failures on Firstout login).

## Code landmarks

`apps/firstout/AGENTS.md`; backend `app/services/auth.py`, `app/permissions.py`, auth middleware, `database.py` `register_rls_hook`; models `team`, `user`, `role`, `team_settings`, `document_sequence`, `location`, `sku`, `customer`, `cin7_import_run`; Cin7 jobs and `cin7-imports/{id}.zip`; Next `next.config.ts` `/api` rewrite to `API_URL`; `sku-label-print.ts`, `print-bin-labels.ts`, `print-html.ts`. Alembic heads at `078_password_reset`. Shared `f0rge_db` today sets `app.user_id` (Marrow-style) and Firstout has no `ENABLE ROW LEVEL SECURITY` yet.

## Out of scope unless a new yes arrives

Live payments or live billing products; Clerk Billing; Cloudflare for SaaS / custom customer domains; Cloudflare Advanced Certificate Manager; extra Railway plugins or a second Postgres; per-tenant databases or schemas; folding trade-portal auth into Clerk; any paid add-on beyond Railway Pro.
