# Customer history and guest-order claim walkthrough — 2026-10-01

The issue #751 server boundary was exercised with a fresh disposable local
PostgreSQL database and Redis instance. Medusa migrations and the Storefront
bootstrap ran against that database. Two synthetic Clerk identities were
signed with an ephemeral RSA key using the configured test issuer and audience;
an unverified identity was also exercised. No Clerk tenant, customer data,
Firstout service, production payment, or production infrastructure was used.

The live walkthrough completed 39 checks across Medusa and the Next BFF:

- The real Medusa Clerk provider exchanged signed claims and emitted customer
  tokens with `actor_type`, `actor_id`, `auth_provider`, issuer, subject, and
  verified-email metadata. An unverified email was rejected.
- Native customer and order routes denied missing BFF credentials, including
  encoded auth-provider paths and case-variant `/STORE/...` paths. Native order
  history stayed actor-scoped; caller-supplied `customer_id`, guessed IDs,
  owner-field probes, double-encoded detail routes, and encoded transfer paths
  did not expose another customer's order.
- A seeded order row in the migrated Medusa schema was explicitly marked as a
  new guest checkout with a confirmation digest. Only the matching verified
  identity could see and claim it. The claim ignored body-supplied email and
  customer ID, repeated claims were idempotent, and a second identity could
  not claim or retrieve it.
- Guest status required the order-bound capability. A signed guest receipt
  worked before logout; logout expired cart, cart-order, and email-receipt
  cookies at their configured paths. Afterwards, account history, account
  detail, and receipt-browser requests were denied without a reusable customer
  session.

The seeded order was deleted after the walkthrough. The synthetic customer
identities remain only in the dedicated disposable local database. The checkout
route unit test covers claim-marker creation for a guest cart, marker removal
for an already-owned cart, and preservation of immutable snapshot metadata.
Medusa 2.21.1 `completeCartWorkflow` copies cart metadata to the created order.

The live walkthrough used Node 22.22.0 and npm 10.9.4. Next ran in Webpack dev mode because the
temporary dependency symlink is outside the Turbopack filesystem root.

Useful repeatable checks from this worktree:

```bash
npm run typecheck --prefix apps/storefront/commerce
npm run lint --prefix apps/storefront/commerce
npm run test --prefix apps/storefront/commerce
STOREFRONT_PG_TEST_URL="$DISPOSABLE_STOREFRONT_PG_TEST_URL" \
  npm run test --prefix apps/storefront/commerce -- storefront-order-claims.integration.test.ts
npm run typecheck --prefix apps/storefront/web
npm run lint --prefix apps/storefront/web
npm run test --prefix apps/storefront/web
```

Still open before marking the customer journey acceptance complete: real
Clerk-hosted email-code sign-in and a browser walkthrough that starts from an
actual guest checkout, claims it after verified sign-in, and checks history,
second-account denial, and logout. This environment had no Clerk tenant or OTP
credentials, so the signed local fixtures do not substitute for that human
provider boundary.
