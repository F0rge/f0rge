# Firstout paid-order handoff QA

The handoff keeps a paid Medusa order in a durable order-metadata outbox until Firstout accepts it. The scheduled retry job scans persisted outboxes after service restarts. Firstout records the external gateway tender in Storefront clearing and customer deposits; it posts revenue, invoices and stock only after stock is available.

## Local walkthrough

Use only disposable local PostgreSQL/Redis services, a test Firstout company, and the local Storefront test-payment provider. Set the Medusa `FIRSTOUT_OPS_*` values and Firstout `OPS_COMMERCE_*` values through the local process environment. Do not put credentials in this document or use Peach/Clerk production credentials for the walkthrough.

1. Apply the Firstout migrations through `056_storefront_order_handoffs`, start both services, and sync a published Firstout SKU into Medusa.
2. Stop the Firstout API while leaving Medusa, PostgreSQL and Redis running. Complete a guest collection checkout with the local test provider and replay its captured callback. Confirm the browser receives captured status and the Medusa order has durable handoff state. A corrected serializer can rebuild a failed, payload-less snapshot from the retained paid-order facts before retrying.
3. Stop Medusa. Restart Firstout and Medusa against the same databases and Redis. Let `retry-storefront-order-handoffs` run. Confirm the outbox reaches `imported` and Firstout has one sales order, one invoice, one acknowledgement and a balanced Storefront clearing/deposit journal. Confirm no `SalesOrderPayment` cash/EFT row was created.
4. With one unit available, submit a synthetic local delivery order for two units. Confirm Firstout returns `stock_conflict` and leaves inventory, invoice and acknowledgement unchanged. Use the staff stock-adjustment flow to make the inventory available, then call the staff retry action and confirm the handoff imports once with the delivery amount and tax on the invoice.

## Recorded disposable run

On 2026-09-28, a fresh local Firstout database migrated through revision 056. The browser checkout passed while the Firstout API was stopped and duplicate captured callbacks created one Medusa order. The live query exposed Medusa's BigNumber `numeric_` amount shape; after correcting the serializer, the retained outbox rebuilt a payload and an offline delivery attempt persisted `retry_wait`. Medusa was stopped and restarted against the same PostgreSQL/Redis services. After Firstout returned, the scheduled retry POST returned 201 and the handoff imported once: one invoiced ZAR 1,150.00 order, ZAR 150.00 invoice tax, one stock acknowledgement, one stock unit consumed, zero cash/EFT tenders, and balanced ZAR 1,150.00 debits/credits between account 1150 (Storefront clearing) and account 2300 (customer deposits).

A separate synthetic delivery order requested two units with one available. It stayed in `stock_conflict` with no invoice, acknowledgement or stock change. An owner made an auditable +1 count adjustment and retried it from the staff route; it imported on attempt 2 with a two-line ZAR 2,415.00 invoice (including ZAR 315.00 tax), a single acknowledgement, and no local tender. Both orders ended invoiced with `awaiting_stock=false`; final SKU stock was zero.

The live run used the existing local payment simulator and synthetic test customer data. It did not charge a real payment method or verify Peach/Clerk credentials or their remote webhooks.
