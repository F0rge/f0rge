# #725 Inventory Vellano's storefront readiness

**Map:** [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Ticket:** [Inventory Vellano's storefront readiness](https://github.com/F0rge/f0rge/issues/725)  
**Researched:** 2026-09-19 (Europe/Luxembourg)  
**Scope:** Planning inventory of `apps/vellano` only — no gap implementation.  
**Source of truth for this write-up:** `origin/develop` tree under `apps/vellano` (backend FastAPI `/api/v1`, nested `AGENTS.md`, live OpenAPI at `/openapi.json` — no checked-in OpenAPI artifact).

## Resolution

Vellano is a **strong back-office Operational System of Record candidate** for catalogue SKUs, ZAR prices, location stock, CRM customers, sales orders, picks/deliveries, and SA VAT books — but it is **not yet an SoR the Storefront (Medusa) can integrate against without a commerce contract**. Missing pieces that block SoR use: flat SKUs (no product→variant model), single photo, staff-only inventory/catalogue APIs, no guest/passwordless customer path, no shipping addresses, no inbound sales-channel / external-order ingest, no machine/service credentials, and no channel/source or external IDs on orders. Treat existing trade portal and public lookbooks as **adjacent B2B surfaces**, not the DTC storefront contract.

---

## Capability matrix

Legend: **Ready** = usable as SoR building block with isolation; **Partial** = exists but wrong shape / auth / completeness for DTC storefront; **Gap** = absent or only documented aspiration.

| Domain | Status | What exists today | SoR-relevant gaps |
| --- | --- | --- | --- |
| **Catalogue** | Partial | SKU CRUD; Cin7-shaped CSV import; category string; design/fabric; BOM kits; staff UI `/catalogue` | No product grouping, slug/SEO/copy, publish flags, or public browse/search API |
| **SKU variants** | Partial | Each sellable unit is a flat `skus` row; `design` + `fabric` act as free-text attributes; unique `lower(design), lower(fabric)` | No Product→Variant hierarchy, structured options, or external variant IDs |
| **Prices** | Partial | `retail_ex_vat` / `wholesale_ex_vat`; named price lists; `resolve_unit_ex_vat` (list → trade wholesale → retail) | Ex-VAT storage vs storefront VAT-inclusive; no channel/promo/schedule prices; helpers hardcode 15% |
| **Stock availability** | Partial | `GET /inventory` (on_hand, on_order, sellable, per-location + bins); SO holds / `awaiting_stock`; transfers, stocktakes | Staff auth only; no ATP/promise API; `sellable = on_hand > 0` (any location); no reserved aggregate |
| **Customers** | Partial | CRM retail/trade; billing_address text; credit/hold; price_list; portal users | Password-based portal (map forbids storefront passwords); no guest; no shipping addresses |
| **Sales orders** | Partial | Quote accept → SO; portal draft SO; confirm / deposit / remainder invoice / cancel; stock hold | No staff `POST` create; no channel/`external_id`; deposits `cash\|eft` only; no cart/checkout/shipping fields |
| **Fulfillment** | Partial | Deliveries from invoice/layby/SO (pack→load→tracking→complete); picks; WMS UI | Manual tracking only; delivery does not move stock; no courier rates/labels/collection booking API |
| **Tax** | Partial | `team_settings.vat_rate` (default 0.15); invoice/SO line VAT; VAT201 draft periods | `vat.py` hardcodes `1.15`; no public tax-inclusive price surface; no SARS API (acceptable) |
| **Images** | Partial | One SKU photo upload/serve (resized); lookbook token photo URLs | No gallery/alt/CDN multi-asset; no public SKU photo without lookbook token or staff session |
| **Inbound sales channels** | Gap | Trade portal + public lookbooks + WhatsApp **comms** webhooks | No `sales_channels` / `channel_outbox` implementation; no Medusa/Shopify order ingest |

---

## Domain detail and route/file pointers

OpenAPI: live `GET /openapi.json` (and `/docs`) on `vellano-api`. Tenant header **`X-Tenant-Host`** required on workspace calls. Auth: cookie `vellano_session` or `Authorization: Bearer` **staff JWT** — no API-key / machine principal (`app/middleware/auth.py`).

### Catalogue

| Surface | Pointers |
| --- | --- |
| API | `GET/POST /api/v1/skus`, `GET/PATCH/DELETE /skus/{id}` — `app/routers/skus.py`, `app/services/skus.py`, `app/models/sku.py` |
| Import | `POST /api/v1/imports/preview`, `/commit` — `app/routers/catalogue_imports.py` (Cin7-shaped inventory + optional SOH) |
| BOM | `GET/PUT /skus/{id}/bom` — `app/models/sku_bom_line.py`, kit explode on till/picks |
| UI | `apps/vellano/frontend/src/app/catalogue/` |

**Exists:** `our_ref`, `our_barcode`, `name`, `design`, `fabric`, `category`, lead time, reorder_min, `carton_count`, preferred supplier. Optional opening stock on create.  
**Gaps for SoR:** no long description / materials / dimensions; no web slug or `published` flag; no collection/taxonomy beyond free-text category; no unauthenticated catalogue list.

### SKU variants

**Exists:** Variant-like data is **denormalised onto the SKU** (`design`, `fabric`); uniqueness prevents duplicate design+fabric pairs. Kits are BOM parents, not merchandising variants.  
**Gaps:** Map V1 needs “product detail with SKU-backed variants.” Vellano has only leaf SKUs — Medusa (or a sync layer) must invent product grouping, or Vellano must add a parent product model later. No `option1`/`option2` schema, no colour/size enums, no external commerce IDs.

### Prices

| Surface | Pointers |
| --- | --- |
| SKU prices | `wholesale_ex_vat`, `retail_ex_vat` on `skus`; response also exposes `*_inc_vat` via helpers |
| Price lists | `GET/POST/PATCH/DELETE /api/v1/price-lists`, `PUT .../items`, `DELETE .../items/{sku_id}` — `app/routers/price_lists.py` |
| Resolution | `app/services/pricing.py` → list item → trade wholesale → retail |
| Settings | `GET/PATCH /api/v1/settings` includes `vat_rate`, `home_currency` (ZAR) |

**Gaps:** Storefront V1 wants VAT-inclusive shelf prices; SoR stores ex-VAT. Conversion uses hardcoded `VAT_MULTIPLIER = 1.15` in `app/services/vat.py` rather than `team_settings.vat_rate`. No storefront-specific price list slug, no time-bound promotions.

### Stock availability

| Surface | Pointers |
| --- | --- |
| Inventory rollup | `GET /api/v1/inventory` → `InventorySkuResponse` (`on_hand`, `on_order`, `sellable`, locations/bins) — `app/routers/purchase_orders.py` (`inventory_router`), `app/services/inventory.py`, `app/models/inventory.py` |
| Locations / bins | `/api/v1/locations`, `/locations/{id}/bins` |
| Holds | SO confirm with `hold_stock` → `apply_outgoing_qty`; `awaiting_stock` when short — `app/services/sales_orders.py` |
| Movements | Transfers F2, receive, stocktakes, adjustments (staff ops) |

**Gaps:** Inventory endpoint requires staff auth — Medusa cannot poll ATP without a staff token or a new storefront/service contract. `sellable` is boolean any-on-hand, not channel-allocated or showroom-only. No reservation ID exposed to an external commerce engine beyond SO hold after staff confirm.

### Customers

| Surface | Pointers |
| --- | --- |
| CRM | `GET/POST /api/v1/customers`, `GET/PATCH /customers/{id}` — `app/routers/customers.py`, `app/models/customer.py` |
| Portal users | `POST /customers/{id}/portal-users` (trade only); cookie `vellano_customer_session` — `app/routers/customer_portal.py`, `app/models/customer_portal_user.py` |

**Exists:** `customer_type` retail|trade, email/phone, `vat_number`, `billing_address` (single text), credit limit / on_hold, `price_list_id`, payment terms.  
**Gaps vs map:** Storefront requires hosted **passwordless** identity and must not store customer passwords — portal **hashes passwords**. No guest checkout customer; no structured shipping/delivery addresses; no saved-address list.

### Sales orders

| Surface | Pointers |
| --- | --- |
| Staff | `GET /api/v1/orders`, `GET /orders/{id}`, `POST .../confirm`, `/payments`, `/invoice`, `/cancel` — `app/routers/sales_orders.py` |
| Origins | Quote `POST /quotes/{id}/accept`; portal `POST /portal/orders` → **draft** (no hold until staff confirm) |
| Model | `app/models/sales_order.py` — statuses `draft \| open \| awaiting_stock \| invoiced \| cancelled` |

**Exists:** Line qty + unit_ex_vat snapshot; optional location hold; deposits cash/EFT with GL; remainder tax invoice.  
**Gaps:** No `POST /orders` for staff/integration create with `external_id` / `channel`; no shipping method, delivery address, or fulfillment preference on the SO; payment path is not a PSP capture; unsuitable as Medusa’s order write-back target without new fields and auth.

### Fulfillment

| Surface | Pointers |
| --- | --- |
| Deliveries | `GET/POST /api/v1/deliveries`, `.../pack`, `/load`, `PATCH .../tracking`, `/complete`, `/cancel` — `app/routers/deliveries.py`, `app/models/delivery.py` |
| Picks | `/api/v1/picks` (sales_order source, kit explode, PDF) — `app/routers/picks.py` |
| UI | `/wms`, `/deliveries`, `/picks` |

**Exists:** Source invoice | layby | sales_order; one active delivery per source; optional `tracking_number` / `carrier` free text; carton_count on pack. **No stock and no GL** on pack/load/complete (stock already moved via hold/till/invoice paths).  
**Gaps:** No rate shopping, label purchase, or collection-slot API (aligns with #718 manual/fixed shipping — ops stays in Vellano, but storefront still needs a write path for “ready for collection / shipped”).

### Tax

| Surface | Pointers |
| --- | --- |
| Rate | `team_settings.vat_rate` default `0.15` — `app/models/team_settings.py` |
| Line math | Invoice/SO/till use ex→inc helpers; PDFs read settings rate |
| Compliance draft | `/api/v1/vat201/periods`, `/reports/vat201` — never SARS |

**Gaps:** Dual source of truth (`settings.vat_rate` vs hardcoded `1.15` in `vat.py`) is a sync hazard for any storefront price projection. No tax code / zero-rated furniture edge cases.

### Images

| Surface | Pointers |
| --- | --- |
| SKU | `POST/GET /api/v1/skus/{id}/photo` — `SkuService.upload_photo` / `serve_photo` (`f0rge_storage` resize; local or remote key) |
| Public (token) | `GET /api/v1/public/lookbooks/{token}/items/{item_id}/photo` |

**Gaps:** Exactly **one** photo per SKU (`photo_storage_key`); no gallery, alt text, or stable public CDN URL for Medusa product media sync without auth or lookbook token.

### Inbound sales channels

| Surface | Pointers |
| --- | --- |
| Trade portal | `/api/v1/portal/*` + UI `/trade/*` — B2B draft orders (out of map scope for DTC) |
| Lookbooks | Staff `/api/v1/lookbooks`; public `/api/v1/public/lookbooks/{token}` (+ events, request→quote) — `app/services/lookbooks.py`; UI `/lookbooks`, `/c/[token]` |
| WhatsApp | `GET/POST /api/v1/webhooks/whatsapp/{slug}` — **comms**, not order OMS |
| AGENTS note | Warns not to reuse Shopify `channel_outbox` / `sales_channels` for email — those names are **aspirational**; **no models/routers exist** in tree |

**Gaps (critical for SoR):** No inbound channel registry, no idempotent “upsert order from Medusa”, no stock/price webhooks outbound, no Cin7/Shopify live sync (CSV import only). Fresh catalogue is acceptable per map; **order + stock feedback loop is not**.

---

## What already supports an Operational SoR role

1. **Authoritative SKU identity** (`our_ref` / UUID) with barcodes and category — good sync key if Medusa stores `metadata.vellano_sku_id`.
2. **Location-level stock and holds** — real warehouse truth once a channel reservation maps to SO confirm/hold.
3. **Sales order → pick → delivery** ops chain and tax invoices / VAT201 — back-office fulfillment after commerce checkout.
4. **ZAR + 15% VAT books** and price lists — finance SoR for post-order accounting.
5. **Tenant isolation** (Option C) and live OpenAPI — API-first boundary for a later Odoo swap, *if* the commerce contract is additive and stable.

## Top gaps that prevent Storefront SoR use today

1. **No inbound commerce channel** — cannot accept Medusa (or any) paid orders as first-class documents with external IDs / idempotency.
2. **No product–variant model** — flat SKUs force grouping and option UX into Medusa or a future Vellano schema change.
3. **No storefront-safe catalogue / ATP APIs** — catalogue, inventory, and photos are staff-session (or trade-password / lookbook-token) scoped.
4. **Customer identity mismatch** — portal passwords vs map’s passwordless/no-password rule; no guest or shipping addresses.
5. **Weak media & merchandising** — single image, no publish/SEO/copy fields for a DTC experience.
6. **No machine credential** — Bearer only works for staff JWTs; no scoped service account for the commerce engine.
7. **Payment/deposit model is cash|EFT books** — not PSP capture hand-off (Peach/Payfast live in Medusa per #718); write-back must record “already paid” without pretending Vellano charged the card.

## Suggested boundary inputs (for later map tickets — not decisions)

- **Commerce engine owns:** cart, guest checkout, passwordless customer accounts, hosted payment, storefront catalogue presentation, shipping option selection at checkout.
- **Vellano owns (once contracted):** SKU master + cost, location ATP, post-order SO/pick/delivery/invoice, VAT books.
- **Must be designed next:** sync direction for products/prices/stock; order ingest API shape; whether variants are projected in Medusa only or modelled in Vellano; service auth.

---

## Key path index

| Area | Backend | Frontend |
| --- | --- | --- |
| Nested agent rules | `apps/vellano/AGENTS.md`, `CONTEXT.md` | — |
| App mount | `apps/vellano/backend/app/main.py` | Next standalone `:3003` |
| SKUs / photos | `routers/skus.py`, `services/skus.py`, `models/sku.py` | `src/app/catalogue/` |
| Imports | `routers/catalogue_imports.py` | `src/app/import/` |
| Price lists | `routers/price_lists.py`, `services/pricing.py` | `src/app/price-lists/` |
| Inventory | `routers/purchase_orders.py` (`inventory_router`), `services/inventory.py` | catalogue Stock tab |
| Customers / portal | `routers/customers.py`, `customer_portal.py` | `src/app/customers/`, `src/app/trade/` |
| Sales orders | `routers/sales_orders.py`, `services/sales_orders.py` | `src/app/orders/` |
| Quotes / lookbooks | `routers/quotes.py`, `lookbooks.py`, `public_lookbooks.py` | `src/app/quotes/`, `lookbooks/`, `c/[token]/` |
| Deliveries / picks | `routers/deliveries.py`, `picks.py` | `src/app/deliveries/`, `picks/`, `wms/` |
| Tax | `services/vat.py`, `routers/vat201_periods.py`, `models/team_settings.py` | `src/app/vat201/`, invoices |
| OpenAPI | `/openapi.json` (runtime) | — |
