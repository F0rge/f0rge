# Paystack checkout and refunds

DasKasas takes card payments through Paystack's hosted checkout, using its own
Medusa payment provider (`pp_paystack_checkout`). It replaces the Peach
integration, which never went live. The community `medusa-payment-paystack`
plugin is not used: it sends refunds without a reference, so a retried request
could refund twice, and it checks only the legacy webhook header with a plain
string comparison and no replay window.

Card payment in full is the only checkout mode. Deposits and a later balance
payment are not built yet; a second payment can use a new initialize/verify
transaction when they are.

## Configuration

Paystack stays disabled until both required values are set in the commerce
environment. Setting only one fails startup.

| Variable | Value |
|---|---|
| `PAYSTACK_SECRET_KEY` | `sk_test_…`, or `sk_live_…` together with `PAYSTACK_LIVE_ENABLED=true` |
| `PAYSTACK_WEBHOOK_SECRET` | The webhook signing secret (`whsec_…`) from Developers > API configuration |
| `PAYSTACK_LIVE_ENABLED` | `true` only when a live key is intended; any other value rejects `sk_live_` |
| `PAYSTACK_HOSTED_TEST_MODE` | `true` allows a `sk_test_` key on a hosted runtime, for a private test-mode walkthrough only |
| `PAYSTACK_REFUNDS_PAUSED` | `true` stops new refund requests; verified outcomes keep converging |

A test key is refused on a hosted runtime (the release image, Railway, or any
setup that is not an explicit loopback-bound local command) unless
`PAYSTACK_HOSTED_TEST_MODE=true`. Paystack publishes its test cards, so a hosted
shop on a test key would let anyone place unpaid orders that reach Firstout for
fulfilment. Keep the preview gate on while the flag is set and remove it after
the walkthrough.

`STOREFRONT_PUBLIC_URL` must be the public HTTPS DasKasas origin, without a
query or fragment, and a live key refuses loopback hosts even over HTTPS; Paystack returns customers to
`<origin>/checkout/paystack-return?reference=…&trxref=…`. Plain HTTP is allowed
only for loopback hosts with a test key outside `NODE_ENV=production`. Keep every
Paystack value server-side.

In the Paystack dashboard, set the webhook URL to
`https://<commerce host>/hooks/paystack`. That route needs a narrowly reachable
commerce ingress; this change does not modify Railway. Medusa's generic
`/hooks/payment/paystack_checkout` route is blocked.

## Payment flow

1. Checkout prepares the bag, then creates a payment session with the
   customer's email (Paystack requires it).
2. The provider stores an attempt with our reference (`dk_<32 hex>`) before it
   calls `POST /transaction/initialize`. Paystack rejects a reused reference, so
   a timed-out request cannot create a second transaction. A timeout, 5xx or
   unreadable response leaves the attempt `initiation_unknown`; the same bag
   never starts another attempt.
3. The browser goes to `checkout.paystack.com`. Its return is never payment
   proof.
4. A `charge.success` webhook is accepted only with a valid `Paystack-Signature`
   (HMAC-SHA512 over `t.rawBody` with the signing secret, a 300-second window,
   any of several `v1` entries, constant-time comparison). The legacy
   `x-paystack-signature` header is ignored. The body is only a trigger: the
   processor calls `GET /transaction/verify/:reference` and acts on that answer.
5. A scheduled job verifies open attempts, including `initiation_unknown` and
   declined ones, because Paystack sends webhooks only for successful charges and
   its hosted page lets the shopper retry another card after a decline. It checks
   every minute for the first hour, then every 15 minutes, and stops after 72
   hours (Paystack's live webhook retry horizon). An attempt still uncertain
   then becomes a terminal `unknown_payment` exception for staff; their repair
   action re-verifies it regardless of age.
6. A verified fact enters the durable inbox, deduplicated by its normalized
   content (Paystack has no event ID and re-signs retries). Only a `success`
   whose amount and currency exactly match the stored attempt and Medusa session
   captures the payment and completes the cart, under the inventory lock. The
   provider's own webhook and authorize methods read only the reference from
   any payload, then require the stored captured attempt and its verified paid
   observation; amount, currency and state in a body are ignored. A
   mismatched paid amount is kept for staff review and no order is created.
   A success after the hold expired, or after the bag changed, becomes a paid
   exception with the original checkout snapshot.

Webhook bodies and verify responses contain customer and card details. The
inbox keeps only the reference, Paystack IDs, amount, currency, status,
timestamps and digests.

## Refunds

Firstout staff authorize refunds; Medusa dispatches them.

1. Medusa records the command locally. It refuses, without contacting
   Paystack, unless the charge reference is our captured attempt for the same
   order; Firstout then shows the command as unknown. Otherwise it asks Firstout
   to move it to `dispatching`, and no request reaches Paystack until Firstout
   confirms that exact amount.
2. `POST /refund` sends the charge reference, the amount and our refund reference
   `dkr_<request id>`. Paystack accepts a reference once, so a repeated request
   returns 409 instead of a second refund. A 409 is read back with
   `GET /refund?transaction=…`, never re-posted.
3. A timeout, 5xx or unverifiable response marks the request `unknown`. The
   worker never re-posts it; it re-reads Paystack each minute and binds any
   refund carrying our reference. If Paystack's numeric charge ID was never
   stored, it reads each open request by our refund reference instead.
4. `refund.*` webhooks are triggers: the processor lists the charge's refunds
   from the API. A refund without our reference (for example one made in the
   Paystack dashboard) is delivered to Firstout without a request ID, so
   Firstout records it for review instead of guessing.
5. `processed` becomes a native Medusa refund, order transaction and credit line
   through a one-use capability; Medusa's admin refund action is otherwise
   refused. `pending`/`processing` and `failed` update the customer status.
6. `needs-attention` means Paystack needs the customer's bank details. Firstout
   shows the refund as needing review, and the commerce exception scan reports
   it. A staff member completes it in the Paystack dashboard; this code never
   calls `retry_with_customer_details`. The later `processed` result converges
   normally.

Refund status emails use the existing SendGrid configuration and
`STOREFRONT_SENDGRID_REFUND_TEMPLATE_ID`.

## Disable and recover

To stop new refund requests, set `PAYSTACK_REFUNDS_PAUSED=true` and restart the
commerce worker. To stop new payments, remove both Paystack values; a stored
attempt or refund then stays visible to the exception scan but is no longer
reconciled automatically.

Do not delete attempt, inbox, refund-dispatch, Firstout journal, Medusa refund,
credit-line or notification-outbox records as a rollback. They are financial
audit and idempotency evidence. Roll back code by deploying the previous version
and keep the tables. Reconcile every `unknown` or `needs_attention` refund in the
Paystack dashboard before resuming.

The earlier Peach tables (`storefront_peach_*`) are no longer used or migrated.
Dropping them needs separate approval.

## Verification status

Paystack credentials do not exist yet. The integration is built against the
documented API (initialize, verify, refund, list refunds, webhook signatures,
checked 21 November 2026) with mocked HTTP. Unit tests and the isolated
PostgreSQL inbox tests cover signature checks, amount matching, idempotency and
the refund barrier. Before taking real money:

1. Record one real test-mode webhook delivery (headers and raw body) as a test
   fixture, and confirm the `Paystack-Signature` format (`t=…,v1=<kid>:<hex>`)
   and the `whsec_` secret prefix against it. The unit tests sign with our
   reading of the documentation, not a captured delivery.
2. Run a test-mode purchase, a closed-browser webhook, a duplicate webhook, a
   failed card followed by a successful retry, a partial refund, a duplicate
   refund request and a timeout against Paystack test mode.

Sources: [Accept payments](https://paystack.com/docs/payments/accept-payments/),
[Verify payments](https://paystack.com/docs/payments/verify-payments/),
[Webhooks](https://paystack.com/docs/payments/webhooks/),
[Refunds](https://paystack.com/docs/payments/refunds/),
[Refund API](https://paystack.com/docs/api/refund/).
