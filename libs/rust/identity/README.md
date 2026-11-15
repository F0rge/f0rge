# Verified Cloudflare Access identity

Shared Rust/Actix identity plumbing for apps choosing the personal approved-person
mode in P-035/P-036. This crate verifies Access assertions; it does not choose an
app's allowed identities, database models, business rules or gateway routes.

An app constructs `Auth` with its exact Access issuer/application audience and
approved email set. Only RS256 assertions from the issuer's JWKS are accepted;
signature, key ID, issuer, audience, expiry, not-before, subject and signed email
are checked. Plain email headers and bearer strings grant no authority.

`Principal` exposes the verified issuer-scoped subject. Apps may configure a typed
expected-identity header to fence stale requests. `ExpectedPrincipal` requires that
precondition on mutations; it is compared against the verified identity and grants
no identity or permissions by itself. App-owned persistence still scopes every
state operation to the verified subject.

Production configuration requires HTTPS Cloudflare team/JWKS origins. Explicit
local mode permits only loopback HTTP fixtures for tests; production deployment
preflight rejects local mode. Test fixtures never contact Cloudflare or send email.

Run `npx nx run-many -t=format-check,lint,test,build --projects=f0rge-identity`.
The committed standalone lock, fixed Rust/Nx targets and shared dependency edge
keep the module covered by affected CI. Real Cloudflare application/policy, secret
custody and origin-bypass verification remain required before activating an app.
