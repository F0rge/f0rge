# #724 — API-first commerce boundary (resolved)

Map: [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)

## Decision

Stable boundary between **Storefront**, **Commerce Engine (Medusa v2)**, and **Operational SoR (Vellano today → replaceable)**.

| Concern | Authoritative | Notes |
|---|---|---|
| Cart / checkout ATP | Medusa | Synced from Vellano; fail closed if stale beyond short TTL |
| Paid DTC order | Medusa first | Idempotent upsert into Vellano with Medusa external id |
| Checkout price (ZAR VAT-inc) | Medusa | Synced from Vellano baseline; no live Vellano price in hot path |
| Sellable catalogue projection | Medusa | Product/variant, copy, images, collections, SEO, publish flag, price, ATP |
| Ops SKU / cost / warehouse detail | Vellano | Not required on storefront |
| Login | Clerk Hobby | Passwordless; no passwords in our apps |
| Commerce customer | Medusa Customer | Linked via custom Auth provider to Clerk |
| CRM customer | Vellano | Upsert on first paid order (email + external ids) |
| DTC promotions / sale overlays | Medusa | Vellano price lists remain ops baseline |
| Fulfillment status (customer-facing) | Medusa (mapped) | Vellano pushes into Ops Commerce API |
| Replace-Vellano seam | Versioned Ops Commerce API `/v1` | Additive only; breaks need `/v2` + dual-run; Medusa never imports Vellano types |

## Failure & sync

- Peach success + Vellano upsert fail → Medusa stays paid/awaiting sync; retry + alert; no auto-refund; manual reconcile queue.
- Stock sync V1: **pull** Vellano→Medusa on short interval (1–5 min); push optional later.
- Idempotency: Peach payment intent root key → Medusa order id → Vellano upsert by external id; stock by SKU + revision/timestamp.

## Grilling

Q1–Q12 accepted as recommended (2026-09-19, Leonardo).
