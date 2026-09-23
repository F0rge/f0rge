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
The private Storefront has no checkout or payment in this first slice.

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
