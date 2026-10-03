# Storefront refunds

Refunds start as an authorized Firstout staff request. Firstout reserves the
remaining refundable amount and returns a durable command to Medusa. Before
Medusa sends the Checkout Classic refund request, it records the local intent
and asks Firstout to move that exact request to `dispatching`. A lost or
ambiguous provider response is marked unknown for reconciliation; the worker
does not automatically repeat a money-moving POST. A verified Peach response
or webhook is delivered to Firstout and then converged into Medusa's native
Payment refund, Order refund transaction, credit line, customer status, and
notification outbox. Local repair never posts to Peach again.

For orders without an invoice, staff may request an authorized amount and can
select refundable line items or cancellation where the staff screen allows
those choices. An order that has been invoiced is restricted to an amount-only
refund after an accepted, completed stock return has a persisted credit note;
its amount is capped by that credit note. An invoiced refund does not cancel
the order or release inventory. A pre-invoice cancellation releases only its
matching pending commitments after the cancellation is accepted.

## Configuration and email template

Configure the Checkout Classic sandbox merchant fields in the commerce service:
`PEACH_ENVIRONMENT=sandbox`, the sandbox merchant/entity IDs, and the dedicated
`PEACH_CHECKOUT_SECRET`. That HMAC key signs and verifies Checkout Classic
refund requests/responses. It is separate from `PEACH_CLIENT_SECRET` (OAuth)
and `PEACH_WEBHOOK_SECRET`; do not reuse either key. Refund signing is disabled
when the Checkout secret is missing. OAuth availability is not a prerequisite
for a signed Checkout Classic refund. The live Peach environment is unsupported.

If refund-status email delivery is enabled, configure the existing SendGrid
API key and sender plus `STOREFRONT_SENDGRID_REFUND_TEMPLATE_ID`. The dynamic
template consumes `order.reference`, `order.fulfillment_promise`,
`refund.amount_minor`, `refund.currency_code`, and `refund.status`. The durable
notification outbox is part of the local refund convergence; an outbox entry
being queued does not prove that SendGrid accepted or delivered the email.

## Disable and recover

To stop new provider refund requests, remove or blank `PEACH_CHECKOUT_SECRET`
and restart the commerce worker. Do not set an undocumented enable flag. The
worker will continue reconciling verified provider observations already
received, but will not start a new Peach refund POST. Keep the environment
configuration and worker stopped if an incident requires halting all refund
processing, and use Firstout/Peach reconciliation before resuming.

Do not delete dispatch, inbox, Firstout journal, Medusa refund, credit-line, or
notification-outbox records as a rollback. They are financial audit and
idempotency evidence. To roll back code, deploy the prior application version
while preserving those records; do not roll back the refund schema while any
refund row exists. Resume only after reconciling each unresolved request against
Firstout and Peach. Unknown requests must not be resent automatically.

## Verification status

Local PostgreSQL and live local Firstout HTTP tests use synthetic provider
responses. They prove the request barrier, native Medusa accounting, duplicate
handling, and recovery behavior without contacting Peach. Actual Peach sandbox
credentials/callback reachability and SendGrid credentials are not available
for this change, so sandbox refund acceptance and email delivery remain
release gates. Keep Peach disabled until the sandbox request, signed response,
webhook duplicate, declined request, and ambiguous-timeout reconciliation
walkthrough have been completed.

The October 3 engineering run used the isolated local Medusa/Postgres,
Redis, and Firstout services only. Its native module proof exercised partial
and remaining refunds, signed response ingestion, repeated signed webhook
delivery, interrupted local projection recovery, more than 25 completed audit
rows, and repair while Firstout's refund-command feed returned HTTP 503. It
asserted the native Payment refund, PaymentCollection refunded amount, Order
refund transaction and credit line, the original customer-visible capture
total, the Firstout financial journal, and that Peach received no second POST
for local recovery. Peach itself was simulated with a signed deterministic
response. The local runner and mode-0600 environment files are host-specific
and are not repository artifacts; the runner command is:

```sh
/Users/leo/.npm/_npx/357891e2033dc9b1/node_modules/node/bin/node \
  /private/tmp/run-storefront-native-refund.js
```

For a portable run, set `STOREFRONT_NATIVE_REFUND_LIVE_TEST=1` with local-only
`DATABASE_URL`, `DB_HOST`, `REDIS_URL`, `STOREFRONT_FIRSTOUT_API_URL`, and
`FIRSTOUT_OPS_URL`, plus `FIRSTOUT_OPS_TOKEN`, `FIRSTOUT_OPS_COMPANY_ID`,
`FIRSTOUT_OWNER_EMAIL`, and `FIRSTOUT_OWNER_PASSWORD`. The native test refuses
to run if the database, Redis, or either Firstout URL is not loopback. Never use
a hosted Firstout URL or production database for these synthetic fixtures.

The staff UI walkthrough is recorded in
[`754-staff-walkthrough.md`](./754-staff-walkthrough.md). It used synthetic
fixtures against the local Firstout UI and API only. Accepted sample intents
remain pending in that isolated test database; the dispatcher and Peach were
not used. Actual sandbox refund acceptance, callback reachability, and email
delivery still require their respective credentials and operator setup.

The separate native cancellation proof used the same disposable Medusa/Postgres
boundary with local Firstout HTTP fixtures and blocked provider HTTP. It showed
that a refund alone preserves inventory commitments, while an authenticated
accepted cancellation cancels the native Order and releases only the matching
stocked and made-to-order commitments once; event replay preserves the canceled
state. Its local-only environment is `/private/tmp/storefront-native-cancellation.env`.
From `apps/storefront/commerce`, the focused command is:

```sh
set -a; . /private/tmp/storefront-native-cancellation.env; set +a
/Users/leo/.npm/_npx/357891e2033dc9b1/node_modules/node/bin/node \
  /Users/leo/.npm/_npx/357891e2033dc9b1/node_modules/npm/bin/npm-cli.js \
  test -- --runTestsByPath src/storefront-cancellation-native.integration.test.ts --forceExit
```

Final combined proof (2026-10-03): the native refund journey also applies an accepted cancellation to the captured, fully refunded order. It verifies unchanged original paid total, capture amount/timestamp, refund history, native Payment captures/refunds, refund transactions and credit lines; only matching made-to-order and pending-paid commitments release. The focused integrated test passed with Peach requests blocked.
