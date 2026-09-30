# Peach Hosted Checkout V2 sandbox

The Storefront registers `pp_peach_sandbox` only when every Peach setting is
present and `PEACH_ENVIRONMENT=sandbox`. Live Peach endpoints and credentials
are deliberately unsupported. The local test provider remains an independent,
local-only option.

Set the `PEACH_*` variables from the Peach sandbox account in the commerce
environment, enable HMAC signing for the Checkout webhook, and set
`PEACH_WEBHOOK_URL` to the exact configured HTTPS callback URL ending in
`/hooks/peach`. `STOREFRONT_PUBLIC_URL` must be the public HTTPS Storefront
origin. Do not put provider credentials in web/client variables. The callback
must reach this one commerce route through an approved narrow ingress; this
change does not modify Railway or make the commerce service public.

Checkout initiation creates a durable attempt before sending the Peach V2
request. A timeout or ambiguous response remains `initiation_unknown`; the same
payment session cannot blindly create another checkout. A later signed webhook
can reconcile that attempt using its merchant transaction reference. Payment
events are verified against the exact raw body, configured callback URL, and
HMAC headers before the normalized allowlist is stored in the PostgreSQL inbox.
Cardholder and customer callback fields are not stored. Webhook IDs are
idempotent; conflicting replays are rejected, and event timestamps plus the
captured-state guard prevent older events from downgrading a completed payment.
When a checkout ID is known, the scheduled worker also queries Peach's
read-only V2 status endpoint and validates the checkout ID, merchant reference,
amount, currency, and payment type before adding a normalized status observation
to the same durable processing path. Peach documents that V2 status lookup is
by checkout ID only. If initiation times out before returning one, only a later
signed webhook can reconcile automatically; otherwise the attempt stays
unknown and requires operator reconciliation with Peach. Never start another
payment attempt for that bag.

The JSON initial configuration callback is signature-checked and acknowledged
separately from urlencoded payment events. Peach's Checkout webhook guide does
not document the JSON handshake schema, so accepting a real sandbox handshake
still requires verification before this integration can be called complete.
The browser return only opens the confirmation route; it is never payment
proof. A paid callback after a hold expires records a paid exception instead of
committing inventory that is no longer available.

No Peach merchant credentials are available in the development environment.
The deterministic boundary tests do not replace the required sandbox purchase,
closed-browser callback, duplicate replay, decline, and unknown-outcome
walkthrough. Keep this provider disabled until those steps pass against a
reachable sandbox callback.

Implementation contracts were checked against Peach's official
[Hosted Checkout V2 guide](https://developer.peachpayments.com/docs/v2-checkout-hosted),
[Checkout webhook guide](https://developer.peachpayments.com/docs/checkout-webhooks),
[V2 checkout initiation reference](https://developer.peachpayments.com/reference/post_v2-checkout),
[checkout status reference](https://developer.peachpayments.com/reference/get_v2-checkout-checkoutid-status),
and [response code guide](https://developer.peachpayments.com/docs/dashboard-response-codes).

Local regression tests execute the committed migration in a disposable
PostgreSQL schema. They verify partial-index idempotency, soft-deleted-row
handling, exact amounts above the int32 range, stale-event protection and
rejection of unverified authorization. A verified Peach debit is reported to
Medusa as already captured; separate capture and refund operations are not
supported in this release. These tests do not contact the Peach sandbox.

Medusa's generic `/hooks/payment/peach_sandbox` ingress is disabled, including
URL-encoded forms of the provider name. All Peach callback completion goes
through the custom signature-verified inbox and inventory lock. Live local
HTTP checks returned 404 for both the plain and encoded generic routes; the
provider method also rejects events without a matching durable paid capture.
