# Live Storefront exceptions and repairs

The commerce worker is the source of live payment, hold, handoff, stock,
capacity and fulfillment conditions. It sends complete successful scans to Ops
through the existing company-bound machine credential and host checks. Ops owns
staff permissions, the visible exception queue and durable repair authorization.

All paths below use `/api/v1/ops-commerce/v1` and require the configured
`Authorization: Bearer …`, `X-Ops-Company-ID`, and operational request hostname.
Credentials are never returned to staff or the storefront browser.

Before reporting missing paid orders, the source worker calls the read-only
`POST /orders/status` with `{external_order_ids: [...]}` (1–500 distinct IDs,
maximum 255 characters each). Its `{items: [{external_order_id, status}]}` reply
includes every requested ID in request order. `imported` requires both the scoped
durable handoff and linked sales order to survive. Missing receipts/orders return
`missing`; operational stock conflicts return `stock_conflict`; other incomplete
states return `failed`. This does not expose internal IDs, payment details or
customer data and cannot modify invoices, stock or tender. A native imported
outbox flag alone is insufficient evidence after a restore.

`POST /exceptions/observations` accepts `{observed_at, observations}`. Each
observation includes kind, correlation_id, status (`open`, `aged`, `terminal`),
explanation, safe_action, detected_at, provider_verified and blocks_checkout.
Optional fields are last_error, amount_minor and payment_reference. Timestamps
require an explicit UTC offset. Source scan time must be within five minutes and
must not be in the future. The worker stamps the scan when reading begins; it
must read **every** relevant source successfully before posting. A failed or
partial scan must not send an empty or shortened list.

Identity is `(company, kind, correlation_id)`. A newer complete scan upserts live
rows and resolves live conditions absent from the scan. Older or repeated scans
are ignored by a company-wide watermark, including when there are no open rows.
Fixture and restore rehearsal rows are excluded from this reconciliation. An
invalid action, duplicate identity or invalid timestamp rejects the whole batch.
The response is `{accepted, checkout_allowed}`.

| Kind | Authorized source action |
|---|---|
| aged_hold | release_expired_hold |
| stale_sync | refresh_projection |
| missing_operational_paid_order | retry_handoff |
| unknown_payment | verify_with_provider |
| refund_mismatch | reproject_verified_refund |
| fulfilment_drift | resync_fulfillment |
| capacity_conflict | acknowledge_capacity |

The existing staff `POST /api/v1/storefront/exceptions/{id}/repair` records a
reason and idempotency key. Operational actions require `sales.orders`;
financial actions require `sales.refunds`. For live rows it queues a command,
sets repair_pending and appends a repair_requested audit. It keeps the current
status and checkout block until the source condition clears. Repeating the same
request or requesting another action while one is pending does not create a
second command. Reusing a key with another reason is rejected.

`GET /exceptions/commands` returns pending commands as
`{items:[{id, correlation_id, kind, action, idempotency_key}]}`. The worker invokes
the existing idempotent source action and rereads all sources. Provider
verification is a read-only status operation; the command cannot create a charge
or refund or assert payment success from a staff flag. Unverified or unsupported
conditions stay open. Financial responses retain the existing staff redaction.

After the action, the worker posts a new complete scan **before**
`POST /exceptions/commands/{id}/result` with
`{outcome: "repaired" | "not_repaired", detail}`. Result details are bounded safe
codes, not provider payloads or personal data. A repaired result requires the
condition to be absent in the current accepted scan, with both source scan time
and server receipt after command creation and within the freshness window. A
result alone cannot resolve a condition. Old scans delayed in transit cannot
attest a command's effect. A failed result keeps the condition and its checkout
block and permits a new authorized retry.

Request and result audits remain append-only. Command completion, effect count
and result audit are committed atomically; a repeated result adds no effect or
audit. Different outcomes for the same command are rejected. Locks always acquire
an exception before its command. Scans serialize per company before modifying
exception rows.

The source worker runs every minute with the existing `FIRSTOUT_OPS` credentials
outside test mode; scheduling is disabled in native integration tests. It checks
all paid native IDs in exact-cover `/orders/status` batches rather than trusting
an imported outbox flag. Authorized actions call the actual hold expiry,
projection synchronization, original paid-payload preparation/delivery, read-only
payment status, verified refund reprojection or fulfillment acknowledgement
services before the next complete scan. Captured attempts without a native order,
unverified refunds and identity conflicts stay `not_repaired`, retaining durable
paid facts for operational reconciliation. Repair processing never sends a
provider refund POST.

Migration `061_live_commerce_exceptions` adds live source identity, scan
watermarks and command storage. Existing rows default to fixture and retain their
rehearsal behavior. Roll back application code while retaining this additive
schema after any commands have been recorded; schema downgrade refuses to erase
authorizations and audit history.
