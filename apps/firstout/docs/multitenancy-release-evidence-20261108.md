# Firstout Clerk operational evidence — 2026-11-08

Status at 09:20 UTC: **release gates remain pending**. No serving database
migration, staff import, RLS activation or Clerk feature activation has occurred.
The user authorized the production rollout after tests, free public signup and
explicit staff import preserving passwords and access. This record distinguishes
completed preparation from the remaining release boundary.

## Restored production rehearsal

All production data stayed inside the existing Firstout Railway project and
Postgres service. No public database proxy or workstation dump was created.

| Check | Observed result |
|---|---|
| Serving source | PostgreSQL 18.6; revision `078_password_reset`; one home team; 85 public tables |
| Staff inventory | Seven enabled humans: four owner, two books, one buyer; zero disabled or system identities |
| Encrypted archive | 7,881,904 bytes; custom PostgreSQL archive, 616 TOC entries |
| Archive SHA-256 | `f080c65a77b673f22a622e861b1b55f18f03e0d7571cc152f77d3ad72903231c` |
| Restore | `pg_restore --exit-on-error --no-owner --no-privileges` succeeded into isolated `firstout_clerk_rehearsal_20261108` |
| Baseline comparison | All 85 table counts and exact staff, password, token, role and permission comparisons matched inside the database |
| Migration cycle | `078 → 082 → 078 → 082` passed using actual Railway API CPython 3.11.18 over its private database connection |
| Cutover cycle | `activate → deactivate → activate` passed with a dedicated scratch LOGIN role: NOSUPERUSER, NOBYPASSRLS, no owner membership, no owned application tables |
| Tenant policies | 82 business tables ENABLE + FORCE RLS; no-context role read returned zero rows, authenticated home context returned five roles |
| Legacy grants | Zero mismatches for home role, disabled state, default location or legacy permission source |
| Auth HTTP | Synthetic legacy password login, HttpOnly cookie, identity and protected role read passed through current routes/middleware with the restricted runtime |
| Existing cookie format | Cookie minted for a synthetic identity by the installed pre-change auth issuer was accepted by the new auth implementation |
| Rejection checks | Signed wrong tenant host returned 403; token-version revoked cookie returned 401 |
| Final preservation | Exact stable user/password/token/role-permission comparison still matched after migrations, cutover and removal of the synthetic identity |
| Serving database after rehearsal | Still revision 078 with zero active tenant RLS tables |

The encrypted archive and restricted comparison files are in
`/var/lib/postgresql/data/firstout-clerk-backups/20261108-905` on the existing
Firstout Postgres volume, outside `PGDATA`. Directory mode is 0700; archive,
encryption material and comparison files are 0600. Retain through rollout and
the staff access validation period; the release owner must set the final retention
date before cleanup. Encryption material remains on the same restricted volume,
so this is a tested rollback artifact, not an independent disaster-recovery copy.
Do not publish or copy its contents into the repository.

Source-only rehearsal package SHA-256:
`e17e22d83d97d135e90ea1ea56610be8c437aa726a76f3ad285df2c899e8616a`.
It contained only backend application/migration code, `alembic.ini` and shared
core/db/storage Python sources; no `.env`, virtualenv, photos or storage data.
The remote scratch code/operator environment is restricted under
`/tmp/firstout-clerk-905` on the API service. Its credentials target only the
disposable rehearsal database. Do not use that role or URL for production.

## Clerk, Railway and domains

- Production Clerk issuer `https://clerk.firstout.co.za` has verified DNS and TLS.
  Organisations require membership; slugs are enabled; frontend creation and
  billing remain disabled. Public access is still invite-only pending activation.
- Production API `CLERK_SECRET_KEY` is staged in Railway. The Next.js runtime
  secret is staged as `${{firstout-api.CLERK_SECRET_KEY}}`, without reading the key
  back or baking it into a frontend image. Neither staged change is deployed.
- Actual Railway workspace plan is Pro, allowing the additional domains without
  a paid change. Existing apex/www/API records remain untouched.
- `app.firstout.co.za` and `*.app.firstout.co.za` were attached to the existing
  frontend service. Four exact Railway-supplied DNS records were added in
  Cloudflare: app/wildcard traffic CNAMEs, ACME challenge CNAME and ownership TXT,
  all DNS-only. Both domains have propagated DNS, verified ownership and valid
  completed Railway TLS certificates expiring 2027-02-06.
- Canonical host operation keeps `NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED=false`
  until wildcard routing/TLS smoke passes.
- Existing development Clerk secret is no longer revealable in the dashboard and
  has no local env copy. No new key was created or rotated for QA. Hosted Clerk
  signup is therefore not claimed as a premerge passing test.

## Remaining release boundary

1. Finish full Python 3.11 suite, review and remote CI; preserve the explicit
   hosted-Clerk test limitation until real provider verification passes.
2. Deploy compatible code with Clerk/signup/reconciliation flags off. Verify
   health, legacy login path, build-time public key and server-only runtime keys.
3. Configure the signed webhook, matching proxy secret and dedicated production
   runtime/migration URLs; verify grants and exact serving topology. The scratch
   role is not a production credential.
4. Stop serving traffic during explicit RLS activation and runtime credential
   switch. Never serve multi-tenant traffic concurrently through the owner URL.
5. Verify real Clerk transport/hosted flow using an isolated synthetic organisation
   before public signup. Import all seven humans by explicit Firstout UUID and
   bcrypt digest; preserve local identities, legacy passwords, grants and disabled
   status. The existing home org cap is seven; new organisations remain at five.
6. Enable public verified-email onboarding and reconciliation only after those
   checks pass; run live tenant separation and legacy-path smoke. Staff perform
   their own existing-password sign-ins before any legacy retirement.

Native dashboard configuration currently requires the user to unlock the Mac;
computer use cannot bypass that operating-system handoff. Billing remains off.
