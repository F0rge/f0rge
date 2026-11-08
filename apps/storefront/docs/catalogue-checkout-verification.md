# Catalogue sync and local checkout verification

An empty catalogue and `exception_ops_http_404` have different causes. The
versioned Firstout `GET /api/v1/ops-commerce/v1/products` can return HTTP 200
with an empty list when no eligible SKU is published. Each source SKU must be
explicitly published and positively priced; a product group must also be
published with every mapped member eligible. Commerce additionally requires
available physical stock or a live finite made-to-order offer. Keep these rules,
machine authentication, host binding and tenant isolation intact.

Firstout migration `062_drop_nia_lookbooks` deliberately removed the exception
tables and their API. The old `sync-storefront-live-exceptions` job still called
`/exceptions/observations` and `/exceptions/commands`, causing the 404. That cron
registration is retired. Catalogue sync, hold expiry, order handoff, payment and
refund processing, fulfillment events and notification retries remain registered.
The older exception runbooks describe the retired feature, not a current API.

`src/scheduled-jobs.test.ts` uses Medusa's actual job discovery to verify this
boundary. It failed with the obsolete job present and passed after removal.
Medusa removes a persisted repeatable schedule when its workflow is no longer
registered; after deployment, inspect at least two minute ticks for continued
catalogue sync and absence of repeated exception 404s. A one-time missing-workflow
cleanup message is expected. No manual Redis flush is required.

## Disposable Firstout fixture

Run from the repository root with Firstout's locked Python environment installed.
Use a fresh, dedicated PostgreSQL container; these commands never target a live
database. The fixture refuses a nonempty database and database names outside
`firstout_checkout_*`. It creates model tables and canonical tenant RLS for the
walkthrough; it does not validate Alembic migrations.

```bash
docker run -d --name daskasas-checkout-firstout \
  -e POSTGRES_USER=firstout -e POSTGRES_PASSWORD=local-only-firstout \
  -e POSTGRES_DB=firstout_checkout_local \
  -p 127.0.0.1:15433:5432 postgres:16

apps/firstout/backend/.venv/bin/python apps/firstout/backend/scripts/local_storefront_fixture.py \
  seed --state-dir /tmp/daskasas-checkout-firstout

apps/firstout/backend/.venv/bin/python apps/firstout/backend/scripts/local_storefront_fixture.py \
  serve --state-dir /tmp/daskasas-checkout-firstout
```

Wait for PostgreSQL readiness before `seed`. The API binds to `127.0.0.1:18003`.
The script clears inherited credentials, rejects a `.env` in its state directory,
disables reminder emails and blocks non-loopback DNS/TCP connections. It serves
through a non-owner `NOSUPERUSER NOBYPASSRLS` database role with enforced tenant
isolation. `fixture.json` contains synthetic IDs; `commerce.env` contains the
local machine-API settings. The single fixture SKU costs R1,150 including VAT and
starts with 50 units. Never copy these fixtures or their publication flags into
production.

Use separate disposable Medusa PostgreSQL and Redis instances. Load the generated
`commerce.env` into the guarded local Medusa environment, then run its migrations,
`bootstrap-storefront.ts` and `sync-firstout.ts` before starting commerce and web.
The web checkout suite requires `STOREFRONT_LOCAL_CHECKOUT_QA=true`, loopback app
URLs and a `daskasas_checkout_*` database. Set `STOREFRONT_TEST_SKU_ID` from
`fixture.json`. No provider credentials or real email recipients are needed.

Launch Node commands through the credential and network guard. Keep the runtime
JSON private (`chmod 600`); populate it only with disposable database/Redis URLs,
local fixture settings, bootstrap-generated public key and local simulator flags.
The launcher rejects app `.env` files and external-provider configuration. For
example, with apps already running, execute the real checkout suite from the
repository root:

```bash
python3 apps/storefront/web/scripts/run-local-checkout.py \
  --env-json /tmp/daskasas-checkout/runtime.json --app web -- \
  node ../../../node_modules/.bin/playwright test \
  --config playwright.config.ts e2e/checkout.spec.ts
```

## Acceptance evidence

On 2026-11-08 the isolated walkthrough passed all three checkout tests against
the built Next.js app (`next build` then `next start`), real Medusa, Redis and
Firstout. It covered collection, closed-browser recovery, expired holds,
duplicate submission (one order and reservation), private-order 404, direct
payment and cross-origin 403, no order for failed/pending/unknown payments, and
R175 local delivery with the persisted address and total. Secure/HttpOnly cookies
were retained. These are local simulator results, not live payment-provider
certification.

The commerce suite passed 201 tests (20 explicitly gated integration tests were
skipped); lint had no errors and typecheck passed. The Firstout catalogue seam
passed its two contract tests. The local fixture also rejected non-disposable
database names, nonempty databases, `.env` files and outbound connections, while
the actual API returned 200 for the catalogue, 401 for a wrong token and 403 for
a wrong company.

- Firstout products returns HTTP 200 with the fixture's ID, price and quantity;
  wrong machine token or company remains denied.
- The real Medusa sync imports that SKU and the public shop renders it.
- The real local browser flow exercises success, duplicate submission, recovery,
  delivery and private order access using the explicit test payment provider.
- No outbound provider calls, real payments or emails occur. Hosted environments
  continue to reject the local test payment capability.
- Production publication is a separate, exact-SKU operator decision. Recheck the
  selected tenant, identity, current VAT-inclusive price, stock and previous flag
  before applying it. Retain a private prestate and revision-guarded rollback;
  do not change prices, stock, groups or other SKUs as part of publication.
