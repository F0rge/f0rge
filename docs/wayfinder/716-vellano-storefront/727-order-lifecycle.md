# #727 — Order, payment, and stock lifecycle (resolved)

Map: [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)

## Lifecycle

| Stage | Behaviour |
|---|---|
| Add to cart | No stock reservation |
| Checkout start | Soft hold in Medusa (15–30 min TTL) |
| Peach success | Hard stock commit; Medusa paid order; idempotent Vellano upsert (or reconcile queue) |
| Oversell after pay | Keep paid order; staff flag; no auto-void |
| Refunds | Staff via Medusa/admin → Peach; no V1 customer self-refund after pay |
| Unpaid cancel | Abandon cart; holds expire |
| Paid cancel | Customer request → staff approve → Medusa cancel + Peach refund if owed |
| Peach down | Block pay; keep cart |
| Vellano down after pay | Keep paid + reconcile (per #724) |
| Stale ATP | Fail closed at checkout when sync TTL exceeded |
| Webhooks | HMAC verify; ack fast; idempotent; dead-letter + alert |
| Staff repair | Single commerce reconcile view before launch |

## Grilling

Q1–Q8 accepted as recommended (2026-09-19, Leonardo).
