# Multi-tenancy release risks and remaining gates

The user authorized merge and production activation after verification on
2026-11-08. Compatibility code deployment and public Clerk activation have
separate gates. See [current operational evidence](multitenancy-release-evidence-20261108.md)
and [QA evidence](multitenancy-test-evidence.md); historical implementation-only
HOLD notes do not describe the latest preparation. No paid upgrade is authorized.

- Default `single_home` preserves the current postgres/no-secret legacy deployment and explicitly does not claim DB tenant isolation. Alembic 081 prepares policies only. Separately invoked cutover requires a verified non-owner NOBYPASSRLS runtime connection, matching proxy HMAC secret, and enforced mode. Actual pool topology, restored production backup and staff access must be verified before activation. See the staged runbook; never serve multiple tenants with owner credentials.
- Mutable `app.tenant_id` RLS protects application mistakes under the restricted role, not arbitrary SQL/compromised DB credentials, superusers, BYPASSRLS or table owners. Directory tables use application scope and narrow preauth lookups, not business-table RLS.
- Clerk import and tenant provisioning now have a real backend transport but remain disabled by default. Local tests use synthetic providers; actual provider/hosted-flow checks remain an activation gate. The existing development secret cannot be revealed again, and no key was rotated for QA. Unsupported hashes or provider failures retain legacy access; no email-only linking or forced reset occurs. Preserve all seven existing human staff with a home-only cap of seven; new organisations have five places.
- Signed Clerk webhooks are durably quarantined by Svix event ID until reconciliation is explicitly enabled. Reconciliation uses current provider membership and persisted local invitation approvals. Provider deletion never removes an imported legacy home grant.
- Existing object references remain readable after their owning row passes tenant RLS. New writes are tenant-prefixed; copying and retiring historical objects needs a separate backed-up, verified operation.
- A production backup was encrypted and restored inside the existing Railway boundary. Migration/reversal/reapply, restricted-role cutover/reversal/reapply, synthetic password login and pre-change cookie checks passed on that isolated restore. The serving database remains unchanged at the recorded preparation boundary. Production runtime credentials still require their own coordinated provisioning and verification. Hosted Clerk UI and real staff sign-ins remain required production evidence.
- Billing has no live provider transport, products or charges. Keep it disabled/test-only until merchant-of-record and Engineering/CoS approval are recorded.
- New tenant membership default locations and all business foreign references must stay within the tenant. Changes to identity-directory queries require special review because users/teams/memberships must be resolvable before tenant context is established.

Merge compatible code only after CI and code QA pass, with all Clerk/signup
flags off and `single_home` retained. Do not activate public signup until the
operator cutover and actual Clerk gates pass. Rollback must preserve legacy
users, hashes, token versions, memberships and permission grants. Scoped unique
keys may prevent downgrade after tenants begin sharing natural keys; use the
tested restore procedure instead of deleting data.
