# Clerk-only staff and customer authentication

This is the separate PR requested after the approved PR #917 deployment. It is not authorization to merge or deploy this authentication change. Production currently remains on the existing authentication contract; the live frontend is `ae6acb696adc80ec4ccca34b425d04e29645088e` and API is `ac420d087bb859d27068a27abb0786a76edfb493`.

The requested target is Clerk for every human login, including the trade/customer portal. Staff permissions and customer access remain separate. Existing machine API keys and verified webhook authentication are not interactive login paths.

## Existing access

The read-only production preflight on 2026-11-08 confirmed seven original staff with exact Firstout UUID/Clerk external-ID and email links, enabled passwords, verified primary emails and enabled canonical memberships. None were banned or locked. Local roles, memberships and disabled flags matched. Local permission grants remain authoritative: an imported owner must retain ownership even when Clerk labels their membership `org:member`.

There were zero customer-portal password accounts across the production teams, and 451 trade customer business records. Those records are not login accounts and must remain unchanged. Repeat this inventory before deployment. If an enabled legacy portal account has appeared without an approved Clerk binding, stop and migrate it explicitly; never delete it or claim it by matching email to make the gate pass.

A directory/preflight check is not proof that each person has signed in. Before releasing the authentication cutover, the existing owner and people representing every live role should verify their own Clerk sign-in with their existing password or another verified factor. Record outcomes without credentials. Do not impersonate staff or reset passwords to manufacture passing evidence.

## Authentication and permissions

- Staff APIs require a valid Clerk session, active organisation, exact immutable user link and enabled local membership. Local roles and grants remain unchanged. Old staff cookies and HS256 bearer tokens cannot authenticate, even when a Clerk setting/key is absent.
- Credential recovery, passwords and verified email changes belong to Clerk. Local display names, locations, roles and membership status remain application preferences. Existing IDs, password hashes and token/history rows are retained as data, without a local login/reset path. The historical team session-TTL value is read-only and does not configure Clerk session duration.
- Customer APIs require an active Clerk identity plus a specifically approved customer/organisation binding. A customer invitation does not create a staff `User` or `Membership`, confer staff permissions or consume staff places.
- Invitation acceptance requires an expiring one-use capability and the canonical verified recipient. The invitation URL carries its secret in a fragment, consumed into a bounded per-tab handoff; Clerk return URLs carry no capability, and acceptance posts it in the request body. Email alone never claims an existing account. Subsequent access follows the immutable subject binding, so verified email changes do not remove access.
- Multiple customer bindings require explicit selection validated against the signed subject. A host, query parameter or selected access ID cannot grant another organisation's data. Pending sessions do not authorize customer or staff business data.

## Provider configuration gate

The existing Clerk instance currently requires organisation membership. The customer design uses Clerk Personal Accounts alongside Organisations, so this setting must become **Membership optional** as a separately reviewed release step. Staff business APIs still require an enabled organisation membership. Active personal/no-organisation sessions can use staff onboarding to create or select a workspace before entering those business APIs. Do not add customers to staff organisations to satisfy the provider's task.

This PR does not change live Clerk configuration. Before activation, verify Personal Accounts/session semantics against the configured instance, including an active no-organisation customer session and rejection of pending sessions. Keep verified email, required credentials, server-controlled organisation creation, five-place defaults, the existing seven-place home organisation and disabled billing. No new Clerk application, paid upgrade or JWT-template workaround is required.

Official references: [Clerk organisation configuration](https://clerk.com/docs/guides/organizations/configure), [Clerk session tasks](https://clerk.com/docs/guides/configure/session-tasks).

## Release verification

1. Pass the PR's real signed-Clerk JWT/JWKS, legacy-cookie/bearer rejection, role, customer/staff separation, invitation expiry/revoke/replay and cross-tenant RLS checks. Use synthetic identities and external-network test boundaries; do not replace authentication dependencies or fake successful retired HTTP routes.
2. Rehearse the additive migration on a disposable database with separate migration-owner and restricted runtime connections. Confirm existing users, customer records, hashes and grants are preserved. The two new identity directories need explicit runtime DML grants; those grants do not make the business tables public or remove FORCE RLS.
3. Repeat the staff and portal-account readiness inventory and personal role sign-in checks. Take and test the approved same-boundary snapshot before production schema preparation, following the existing runbook. Freeze legacy credential creation during the final readiness/cutover window so a new unbound portal account cannot appear between the check and release.
4. After explicit release approval, prepare revision 083 with the migration owner while the compatible old API remains available. Grant only the required new-table privileges to the actual runtime role. In the observed production topology that role is `firstout_app`:

   ```sql
   GRANT SELECT, INSERT, UPDATE, DELETE
     ON TABLE public.portal_access, public.portal_invitations
     TO firstout_app;
   ```

   Confirm the target and role before running this; local/test role names differ. Application startup and the preflight validate privileges but never grant themselves ownership or bypass.
5. Run the new code's read-only gate using the restricted runtime URL and server-only Clerk settings, after schema/grants are prepared:

   ```bash
   cd apps/firstout/backend
   uv run python -m app.commands.clerk_only_preflight
   ```

   It must report readiness and exit successfully. Missing schema/grants, broken staff bindings or an enabled legacy portal account without an approved binding stop the release. Never print database URLs or credentials. This command does not log staff in or prove their personal passwords.
6. Apply the reviewed Personal Accounts setting and deploy the exact CI-tested merged sources with server-only secrets. Verify both staff and customer flows and that old cookies, passwords and HS256 tokens cannot enter either flow. All onboarding/enrollment side effects require active sessions as well; unfinished MFA/recovery tasks stay with Clerk.
7. Preserve tenant enforcement and data on failure. Do not silently restore password authentication, grant customers staff membership or disable RLS as a recovery mechanism. Any rollback that reintroduces a legacy login requires a separate explicit decision.

The historical dual-auth instructions in the [multi-tenancy runbook](multitenancy-deploy-runbook.md) describe the earlier rollout. Once this cutover is released, old cookies must be rejected, including previously unexpired cookies. The user explicitly requested their retirement in this new PR. Current production remains unchanged until that separate release.

## Hosted walkthrough before merge and activation

Local signed-token/API tests and configured Clerk SDK builds do not establish that the hosted provider finishes the customer journey. Keep the PR in draft until this verification is recorded against a suitable configured test instance:

- An invited, verified customer without a staff organisation completes Clerk signup/sign-in and accepts the invitation; the fragment capability never enters Clerk redirect parameters.
- The customer sees only approved business/customer bindings, selects the intended account, loads its catalogue and creates an order for that customer. Switching accounts clears the previous catalogue and quantities.
- A wrong recipient, expired/revoked invitation and revoked customer access show a useful error without exposing another customer's data. Backend logs show no unexpected 500s.
- Existing staff representing each live role complete their own Clerk sign-in and reach the same organisation and permissions. An imported local owner with Clerk's generic member label retains owner access.
- Pending MFA/recovery sessions, old staff/customer cookies and local-password requests cannot enter either portal. Sign-out ends the Clerk session even if stale-cookie cleanup fails.

Do not change production provider settings or reset/impersonate existing staff merely to close this ticket. A separately approved production release still requires the readiness and schema checks above.

## PR validation evidence

- Backend: the full suite passed on CPython 3.11.18: 766 tests, two warnings, 163.13 seconds. Pinned Ruff 0.16.1 lint/format and Git whitespace checks also passed.
- Frontend: 122 tests, TypeScript checks and lint passed (four existing image warnings). Both the missing-key and configured official Clerk SDK production builds passed with 57 routes. The configured build used the public publishable key without a server secret in the build input.
- A real local browser walkthrough checked `/users`, `/login`, `/trade/login` and `/trade/catalogue` with the Clerk key absent. Each showed the unavailable message, with no password form or protected data and no browser warnings/errors. This is a denial-path check, not hosted sign-in evidence.
- The migrated restricted-runtime matrix exercised valid signed Clerk requests, legacy rejection, tenant/customer isolation, the one-connection-pool customer chooser, composite tenant foreign keys and explicit directory grant/revoke checks. The chooser connection-pool failure found during QA was fixed without increasing the pool or changing RLS.
- Independent production-source review found no confirmed authentication bypass, tenant leak or existing-access loss. Its thin-router finding was resolved by moving dependency resolution and response enrichment out of the router.
