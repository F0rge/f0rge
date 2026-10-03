# Storefront restore rehearsal and recovery

Issue #760. Operators restore commerce state into an isolated environment and
reconcile provider, order, stock, and capacity truth before checkout reopens.
This document is the operator procedure. It does not record a live restore.

## What this change does not claim

Medusa is not deployed for this issue. No backup was taken from a live
database, and no snapshot was loaded into Medusa, Railway, or Firstout. The
recovery-environment walkthrough (backup, sandbox payment, restore, blocked
checkout, reconciliation, reopening) is unmet. Measured times below come from
the in-process rehearsal clock in the tests, not from a hosted restore.

Do not treat the cadence in the next section as an agreed business SLA.

## Proposed cadence

| Item | Proposal | Status |
| --- | --- | --- |
| Copies retained | 14 daily copies | Proposal, not an agreed SLA |
| Recovery point | At most 24 hours | Proposal, not an agreed SLA |
| Restoration after the operator starts | 4 hours | Proposal, not an agreed SLA |

The 24-hour figure gates a stale-backup alert so an old copy is not treated as
fresh. The 4-hour figure is recorded on the rehearsal clock and is not a
pass/fail SLA. A rehearsal that takes longer still reports
`within_proposed_restoration: false` and `agreed_sla: false`.

Fixture clock used by the tests (not a hosted restore):

| Measurement | Value |
| --- | --- |
| Backup captured | 2026-10-02T16:00:00Z |
| Rehearsal clock | 2026-10-03T12:00:00Z |
| Backup age | 20 hours (72,000,000 ms), inside the proposed recovery point |
| Operator start to finish | 12 minutes (720,000 ms), inside the proposed restoration window |
| `live_restore` | false |

## What a protected backup includes

Durable commerce and integration state, in object storage that is separate
from the live store bucket:

- `commerce_postgres`
- `payment_attempts`
- `refund_ledger`
- `order_handoff_outbox`
- `notification_outbox`
- `capacity_reservations`
- `ops_exception_queue` (the Firstout exception queue from issue #755)

Credentials stay in the secret store. A manifest with `credentials_included:
true` is corrupt and must not be restored. Redis is cache and is emptied on
restore; it is not a durable dataset. Do not back up or restore the Marrow
project, and do not drop or rename a Postgres database named `railway`.

The backup bucket is not provisioned by this change. `POST
/api/v1/storefront/exceptions/recovery/backup-check` validates a manifest and
writes a redacted alert. It does not read object storage and it does not
restore data.

## Failure alerts

Missing, corrupt, and stale manifests write a redacted alert on the existing
`storefront_exception_alerts` table. The message names the route and the safe
action. It does not include customer email, payment amount, card data, or
secrets. The same table carries these operator routes:

| Route | Operator action |
| --- | --- |
| `stale_stock` | Refresh the projection. Do not decrement stock again. |
| `aged_paid_handoff` | Replay the existing handoff key. Do not create a second order. |
| `webhook_failure` | Replay the stored callback only after provider verification. |
| `job_failure` | Restart resumes the same idempotency key. |
| `email_failure` | Replay the notification key. Do not send a second message. |
| `spending` | Operator review. No customer or payment data is included. |
| `backup_missing` / `backup_corrupt` / `backup_stale` | Do not restore that copy. |

Checkout stays gated while any of these are unresolved as restore rows.

## Isolated restore

1. Keep the storefront private and non-indexable. Disable new payment attempts.
2. Restore only into a clean isolated database. Do not overwrite live data.
3. Leave credentials out of the dump. Inject them from the secret store after
   the restore.
4. Open a recovery set on the existing exception queue. This does not create a
   second queue:

```http
POST /api/v1/storefront/exceptions/recovery
{"restore_id":"snap-20261002","later_payment":true,"later_refund":true}
```

That call writes blocking rows on `storefront_commerce_exceptions` for the
later payment (`unknown_payment`), later refund (`refund_mismatch`), order
(`missing_operational_paid_order`), stock (`stale_sync`), and capacity
(`capacity_conflict`). `GET /api/v1/ops-commerce/v1/checkout-safety` stays
`checkout_allowed: false` until those rows are resolved. Paid orders already
captured are kept.

5. Replay provider callbacks and jobs with their original idempotency keys.
   Unverified payment or refund replays do not apply. A second key for an
   effect that already applied does not apply again.

```http
POST /api/v1/storefront/exceptions/recovery/replay
{"restore_id":"snap-20261002","effect":"payment","idempotency_key":"pay-key-1","provider_verified":true,"reason":"Apply payment once during restore"}
```

Effects are `payment`, `refund`, `order`, `operational_posting`, and `email`.
Each reaches 1 and stays 1 across a restart, because the count is rebuilt from
the exception audit rows.

6. Reconcile truths only after the matching effects exist. Stock and capacity
   are acknowledgements: they do not decrement stock or consume capacity a
   second time. Provider reconciliation requires `provider_verified: true`.
   Order reconciliation requires both the order effect and the operational
   posting effect.

```http
POST /api/v1/storefront/exceptions/recovery/reconcile
{"restore_id":"snap-20261002","truth":"provider","idempotency_key":"truth-provider-1","provider_verified":true,"reason":"Reconcile provider for the restored snapshot"}
```

Repeat for `order`, `stock`, and `capacity`.

7. Reopen only when both of these are true:
   - `GET /api/v1/ops-commerce/v1/checkout-safety` returns `checkout_allowed: true`.
   - Commerce can reach Firstout and the stock projection is fresh.
     `GET /api/v1/storefront/exceptions/recovery/{restore_id}?ops_reachable=true`
     records that health check. `ops_reachable=false`, or a failed commerce
     health check, keeps checkout gated even after the queue is clear.
     Passing the query flag does not probe the network by itself.

## Firstout outage

Firstout is a required dependency. While commerce cannot reach it, checkout
stays gated and paid orders stay retained. Do not replay handoffs against a
down ops API, and do not refund a captured payment just because the back
office is down. When Firstout returns, reconcile provider, order, stock, and
capacity on this same exception queue before reopening. Do not create a
parallel queue.

## Restart and replay

| Event | Safe result |
| --- | --- |
| Same payment or refund callback | No second capture or refund |
| New idempotency key for an effect already applied | No second effect |
| Order handoff restart | No second operational order |
| Operational posting restart | No second stock or ledger post |
| Email job restart | No second message |
| Stock or capacity acknowledgement | No second stock or capacity effect |

Financial replay and provider reconciliation require `sales.refunds`. Opening
a restore and reconciling order, stock, or capacity require `sales.orders`.

## Rollback

If validation fails, keep private mode and leave new payment attempts disabled.
Roll the application back to the last verified release without discarding
paid-event history or the exception queue. Reconcile outstanding effects
before reopening. Use an isolated restore, not an overwrite of live data.

## Checks

```bash
cd apps/storefront/commerce && npm test -- --testPathPattern=storefront-recovery
cd apps/firstout/backend && uv run pytest tests/test_storefront_recovery.py -q
```

These tests encode the state machine. They are not evidence that a live
restore ran.
