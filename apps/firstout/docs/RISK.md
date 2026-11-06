# Multi-tenancy release risks and remaining gates

This is a local implementation PR, **not deployment approval**. No paid add-on was purchased or found necessary during fake-provider implementation. No production user import, database mutation, DNS change or Railway configuration change was performed.

- Runtime database role, ownership, inherited owner memberships, actual pool topology and restored production backup must be verified before deployment. Production startup rejects an unsafe runtime role or missing FORCE RLS. Existing runtime owner credentials must not simply be reused.
- Clerk import and tenant provisioning expose injected provider interfaces and are disabled by default. Tests use synthetic providers. A production operator transport, confirmed plan availability and approved import run remain prerequisites. Unsupported hashes or provider failures retain legacy access; no email-only linking or forced reset occurs.
- Signed Clerk webhooks are durably quarantined by Svix event ID during dual-auth. They do not automatically create, delete or alter local grants. Explicit reconciliation/provisioning is required. This deliberately prevents provider deletion events from stripping existing local home access.
- Existing object references remain readable after their owning row passes tenant RLS. New writes are tenant-prefixed; copying and retiring historical objects needs a separate backed-up, verified operation.
- The native local PostgreSQL test server is disposable and uses synthetic data. Non-owner tests prove the policies locally; they do not prove the production role or pool configuration. Hosted Clerk UI and real staff sign-ins remain required production evidence.
- Billing has no live provider transport, products or charges. Keep it disabled/test-only until merchant-of-record and Engineering/CoS approval are recorded.
- New tenant membership default locations and all business foreign references must stay within the tenant. Changes to identity-directory queries require special review because users/teams/memberships must be resolvable before tenant context is established.

Do not merge/deploy until the runbook gates are satisfied and Engineering plus CoS approve. Rollback must preserve legacy users, hashes, token versions, memberships and permission grants. Scoped unique keys may prevent downgrade after tenants begin sharing natural keys; use the tested restore procedure instead of deleting data.
