# Customer account boundary walkthrough — 2026-09-30

The batch was exercised against a fresh local PostgreSQL database and Redis,
with Medusa listening on port 9008. Two synthetic Clerk subjects used a
generated RSA key and the configured issuer, audience, verified email and
authorized-party claims. These fixtures exercise the real Clerk verifier and
Medusa HTTP/database boundary; they do not prove Clerk OTP delivery or a real
customer browser session.

Observed results:

- The Clerk exchange without the BFF secret returned 403 and no token.
- Both signed identities exchanged successfully, created their own customer
  through `POST /store/customers`, refreshed their token, and read `/me`.
  The resulting customer IDs were distinct.
- Customer one created, listed, read, updated and deleted an address. Customer
  two received 404 for reading, updating or deleting that address.
- A guest cart attached to customer one without being replaced. Its owner
  retained access; customer two and an unauthenticated guest were denied.

The first run caught an incorrect `addr_` validation assumption. Native Medusa
customer addresses use `cuaddr_`; the account BFF now accepts that prefix.
An audit of the Storefront source found no other uses of the incorrect prefix.

The new account fields and actions use the shared UI library. The shared
provider and token aliases retain the existing Collector palette and fonts.

Still required before closing #750: a configured Clerk development tenant with
passwords disabled, the documented JWT template, a real email-code sign-in,
and the complete browser journey through guest-cart retention, address reuse,
logout and second-account denial. Local HTTP fixtures do not replace this gate.

Additional local web HTTP checks: `/account` and `/account/sign-in` returned
200 with noindex headers. Same-origin `POST /api/account/logout` returned 200
and expired the cart, order-access and email-order-access cookies; a foreign
origin returned 403 without changing cookies. The production preview gate with
missing credentials returned 503, no-store and noindex. The in-app browser
blocked both localhost and 127.0.0.1 on this QA port (`ERR_BLOCKED_BY_CLIENT`),
so these response checks are not recorded as a completed browser walkthrough.
