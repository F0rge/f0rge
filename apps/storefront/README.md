# Storefront foundation

Separate applications for Medusa commerce (`commerce`) and the Next.js public site (`web`).
Firstout is the operational system; its versioned Ops Commerce API is the only source adapter.

The Medusa setup began from the [official DTC starter](https://github.com/medusajs/dtc-starter)
at commit `e3a237c` (September 2026). The commerce configuration and bootstrap flow use
that starter's supported Medusa v2.21.1 APIs. Its MIT notice is preserved in
`commerce/LICENSE.medusa-dtc`. The public UI is deliberately implemented with the
repository's Next 16 / React 19 and `@f0rge/ui` rules instead of importing the
starter's Radix components or its password-based account pages.

Local ports: Firstout API 8003, Medusa 9000, public site 3004. Use separate
PostgreSQL databases for Firstout and Medusa, plus Redis for Medusa. Configure
`OPS_COMMERCE_TOKEN`, `OPS_COMMERCE_COMPANY_ID` (the Firstout team UUID) and
`OPS_COMMERCE_ALLOWED_HOST` on Firstout. Configure the matching values in the
Medusa environment; secrets must stay server-side. The source starts unpublished;
staff opt in a priced SKU by setting `storefront_published` on the staff API.

Run Medusa migrations and the first-time bootstrap script before the source sync.
The private Storefront supports guest checkout for collection and configured
Gauteng delivery. It applies the configured South African VAT rate to
VAT-inclusive ZAR prices and calculates delivery from server-owned zone/rate
configuration. No launch delivery rates are checked in. The included payment
provider is a deterministic local test simulator; no real payment is taken and
paid-order import into Firstout is outside this checkout slice.

For local development, use independent Firstout and Medusa PostgreSQL databases
and a Redis instance. Copy each `.env.example` to a local `.env`, then set a
disposable Firstout machine token and its Team UUID on both sides. Bind
`OPS_COMMERCE_ALLOWED_HOST` to the hostname used by `FIRSTOUT_OPS_URL`.

```bash
cd apps/storefront/commerce
npx medusa db:migrate
npx medusa exec ./src/scripts/bootstrap-storefront.ts
npx medusa exec ./src/scripts/sync-firstout.ts
npm run dev
```

The bootstrap creates a publishable key; copy it from Medusa Admin into the
Storefront web environment. Start `npm run dev` in `apps/storefront/web` and
visit `http://localhost:3004`. The sync job repeats every minute while Medusa
runs. It serializes runs with the Redis-backed Medusa lock and applies only
newer source revisions. Keep the machine token only in server environments.

To verify the live boundary, set `STOREFRONT_TEST_SKU_ID` to a published SKU UUID,
then run `npx nx run storefront-commerce:integration` and
`npx nx run storefront-web:e2e`. The integration target checks the real Ops
and Medusa APIs, including price/stock parity, field allowlisting, and denial
of a bad service token. The browser target checks navigation and direct 404s.
The Firstout database-backed isolation test is in
`tests/test_ops_commerce_catalogue.py`.

For bag and hold development, set the same server-only `STOREFRONT_BFF_SECRET`
(at least 32 characters) in commerce and web. Browser cart identity is a signed,
httpOnly cookie; Medusa's cart API requires the BFF secret even when a cart ID
is known. `STOREFRONT_SYNC_CRON` defaults to every minute,
`STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS` to 300, and
`STOREFRONT_HOLD_TTL_SECONDS` to 1200. Add-to-bag does not reserve stock;
continuing from the bag reserves it until expiry or cancellation. The expired
hold job checks every minute. Stale source data preserves the bag but blocks a
new hold. The operational acknowledgement and pending paid-commitment contract
is described in `../firstout/backend/docs/ops_commerce_availability.md`.

Configure `STOREFRONT_VAT_RATE_PERCENT` on the commerce server (defaults to
15) and set `STOREFRONT_GAUTENG_DELIVERY_ZONES` only after operations approves
each zone and rate. Its JSON entries have an `id`, `name`, non-empty
`cities`, optional `suburbs` and four-digit `postal_codes`, and
`rate_zar`. With no zones configured, delivery is unavailable and free
collection remains available.

The test payment provider is unavailable on public production or hosted
deployments, even if `NODE_ENV` is misconfigured. For local checkout QA only,
set `STOREFRONT_TEST_PAYMENT_ENABLED=true` and
`STOREFRONT_RUNTIME_KIND=local` in the commerce environment while Medusa runs
with `NODE_ENV=development`, then rerun the bootstrap. Keep both values off in
Railway. Checkout preparation persists an order-confirmation capability before
returning the payment session; only its hash is stored with the cart and paid
order, and the browser receives the capability in an httpOnly cookie. A paid
callback can create the order after the browser closes, and duplicate events
are idempotent.

For live checkout QA, use a disposable local Medusa database and a published
test SKU. Set `STOREFRONT_TEST_CHECKOUT_SKU_ID` in the Playwright process,
along with its public Medusa key, the BFF secret, and the same disposable
Medusa `DATABASE_URL`. Configure a disposable zone and provide
`STOREFRONT_TEST_DELIVERY_CITY`, `STOREFRONT_TEST_DELIVERY_SUBURB`, and
`STOREFRONT_TEST_DELIVERY_POSTAL_CODE` for its address. Run
`npx playwright test --config playwright.config.ts e2e/checkout.spec.ts` from
`apps/storefront/web`. See `docs/747-live-walkthrough.md` for the exercised
success, recovery, delivery, and database assertions.

For the bag browser test, set `STOREFRONT_TEST_BAG_MULTI_SKU_ID` to a published
SKU with at least two units and `STOREFRONT_TEST_LAST_UNIT_SKU_ID` to one with
exactly one free unit. Set `STOREFRONT_TEST_MEDUSA_PUBLISHABLE_KEY` to the local
public key to test direct cart denial. Run `npx nx run storefront-web:e2e`
against the disposable live stack. See `docs/746-live-walkthrough.md`.

The Collector discovery slice uses published Medusa Store API products. Home and
collections lead to `/shop`, where search, category, collection, availability,
price and sort state live in the URL. Product pages show the selected variant's
price, stock or order lead time, gallery, dimensions, material and care. Medusa
Admin owns the merchandising details described in `commerce/MERCHANDISING.md`.
Set `NEXT_PUBLIC_BASE_URL` in the web environment to the site's public origin
before launch; canonical links use it. Only a production Railway environment
with an HTTPS origin permits indexing. Account and checkout pages remain
private and are excluded from indexing.

For discovery browser coverage, publish two representative SKUs, a draft SKU,
and a two-variant group in a disposable local environment. Set
`STOREFRONT_TEST_SKU_ID`, `STOREFRONT_TEST_OTHER_SKU_ID`,
`STOREFRONT_TEST_DRAFT_SKU_ID`, and `STOREFRONT_TEST_GROUP_HANDLE`, then run
`npx nx run storefront-web:e2e`. The tests skip fixture-dependent cases when
their corresponding IDs are absent.
