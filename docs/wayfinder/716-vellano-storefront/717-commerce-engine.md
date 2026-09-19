# 717 — Select the V1 commerce engine

**Parent:** [#716 Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Issue:** [#717 Select the V1 commerce engine](https://github.com/F0rge/f0rge/issues/717)  
**Researched:** 2026-09-19 (Europe/Luxembourg, UTC+2)  
**Primary sources only** (official docs, GitHub, vendor pricing pages).

## Question

Which headless commerce engine should power the V1 Storefront, using Medusa as the benchmark and strong candidate? Compare current Medusa capabilities and operational requirements with credible open-source alternatives and a thin custom layer. Cover catalogue projection, carts, promotions, checkout, payments, customer accounts, order workflows, extension model, Next.js/React fit, Railway deployment, maintenance burden, and realistic monthly cost under the USD 50 platform ceiling. Resolve with a recommendation and the conditions that would invalidate it.

## Context (from #716)

- Vellano SA furniture; V1 market South Africa only; ZAR; VAT-inclusive prices; physical goods; domestic delivery or collection.
- V1 journey: browse/search, PDP with SKU variants, cart, guest checkout, hosted payment, confirmation; optional customer account (order history, saved addresses).
- Auth must be **hosted and passwordless**; the app must not store customer passwords.
- Vellano is initial ops SoR (later replaceable by Odoo/etc.); Cin7 holds current product data but a fresh catalogue is preferred — no Shopify migration.
- Railway preferred host; payment PSP fees outside the USD 50/month platform budget.

## Candidates compared

| Candidate | Licence / model | Stack | Self-host | Managed cloud under USD 50? | Notes |
| --- | --- | --- | --- | --- | --- |
| **Medusa** (benchmark) | MIT (OSS core; separate Enterprise Edition materials) | TypeScript / Node | Yes (Postgres + Redis + server + worker + object storage) | **Yes** — Cloud Develop from USD 29/mo (includes storefront & backend hosting); Launch from USD 99/mo exceeds ceiling | Strong Next.js starter; modular commerce modules; no GMV tax on Cloud |
| **Saleor** | BSD-3 (OSS); Cloud commercial | Python / Django, GraphQL-only | Yes (API + Celery worker + scheduler + Postgres + Redis; Docker preferred) | **No** — Forever Free is non-commercial; commercial Cloud starts at GMV-tier plans (e.g. Volume USD 3999/mo) | Excellent GraphQL/admin depth; heavier ops; stack mismatch for a TS/Next team |
| **Vendure** | GPLv3 Core (commercial Platform optional) | TypeScript / NestJS / GraphQL | Yes; **official Railway deploy guide** | Self-host only for budget; Cloud is design-partner / custom | Strong TS fit; GPL may need legal review; smaller community than Medusa |
| **Commerce Layer** | Hosted SaaS only | REST APIs | **No** on-premise | Developer free tier: 100 live orders/mo; paid is Enterprise custom | Thin commerce API; vendor lock-in; opaque cost above free tier |
| **Thin custom layer** | N/A (own code) | Whatever the monorepo uses | Yes | Infra only — but engineering cost dominates | Reimplements cart/tax/checkout/order state; highest long-term burden |

## Capability matrix (V1 needs)

| Concern | Medusa | Saleor (self-host) | Vendure (Core) | Commerce Layer | Thin custom |
| --- | --- | --- | --- | --- | --- |
| **Catalogue projection** | Product Module (variants, categories, collections); Sales Channel scoping; Admin + Store APIs | Native multi-channel catalogue via GraphQL | Product variants, channels, facets | SKUs / markets / price lists | Build product + inventory tables and APIs |
| **Carts** | Cart Module: addresses, line items, shipping, promotions, tax lines | GraphQL checkout/cart | Order/cart APIs | Carts as first-class resources | Build from scratch |
| **Promotions** | Promotion Module: %/amount, rules, campaigns; tax-inclusive promotions supported | Vouchers/sales in core | Promotions plugin model | Promotions (Enterprise add-on called out on pricing page) | Build rules engine |
| **Checkout** | Documented multi-step Store API flow (email → address → shipping → payment → complete) | GraphQL checkout | Checkout flows via Shop API | Hosted Links / checkout apps | Build + harden state machine |
| **Payments** | Payment Module + providers (official Stripe provider + webhooks); custom providers possible | Multiple gateways via apps/plugins | Payment plugins | Many gateway integrations | Direct PSP integration only |
| **VAT-inclusive ZAR** | Tax Module (tax regions/rates); Pricing Module **tax-inclusive pricing** via `PricePreference.is_tax_inclusive` for `region_id` / `currency_code` | Tax configuration in core | Tax zones/rates | Tax calculators per market | Manual tax math |
| **Customer accounts** | Customer Module (guest + registered); Auth Module (email/password, third-party/social, custom providers) | Customer accounts in GraphQL | Customer accounts | Customers resource | Own user store (conflicts with “no passwords”) |
| **Passwordless auth** | Not a built-in magic-link provider; **custom Auth Module Provider** or third-party IdP is the intended extension path | Apps / custom auth | Strategies / plugins | External IdP patterns | Must use hosted IdP anyway |
| **Order workflows** | Order Module: retrieve/create/cancel; returns/edits/exchanges/claims; draft orders | Mature order + fulfilment GraphQL | Order process / states | OMS suite on paid plans | Build order state machine |
| **Extension model** | Modules, workflows (rollback), API routes, plugins; ERP/sync recipes | Apps + webhooks; discourage forking core | NestJS plugins | Apps / webhooks only | Unlimited but unsupported |
| **Next.js / React fit** | Official Next.js Starter (monorepo with `create-medusa-app --with-nextjs-starter`); JS SDK; React-oriented storefront guides | Official Next.js storefront starter | Storefront starters; GraphQL client | JS SDKs; bring your own UI | Full control |
| **Railway deployment** | Feasible via general deploy guide (Postgres, Redis, server + worker, ≥2 GB RAM recommended); community/Railway issues exist around HOST/healthchecks | Possible with Docker Compose-shaped services; more processes | **First-party Railway guide** (server + worker + Postgres; claims ~USD 5/mo after trial for minimal setup) | N/A (SaaS) | Straightforward Node + Postgres |
| **Maintenance burden** | Medium: Node upgrades, migrations, Redis/worker ops; large community (~36k GitHub stars) | Higher: Python + Celery + scheduler + GraphQL schema discipline (~23k stars) | Medium: NestJS familiarity; GPL upgrade/legal hygiene (~8.5k stars) | Low ops, high vendor dependency | **Highest** eng burden for commerce correctness |
| **Realistic monthly cost ≤ USD 50** | **Medusa Cloud Develop from USD 29** (storefront + backend hosting, no GMV fee) **or** lean Railway self-host (see cost section) | Self-host only under ceiling; Cloud commercial exceeds | Self-host under ceiling (official Railway path) | Free ≤100 live orders; Enterprise unknown | Infra cheap; opportunity cost high |

## Medusa deep dive (benchmark)

### Commerce coverage for V1

Medusa ships commerce domains as modules used by the application APIs, including Product, Pricing, Cart, Promotion, Tax, Payment, Order, Customer, Auth, Fulfillment, Inventory, Region, Sales Channel, and others ([Commerce Modules](https://docs.medusajs.com/resources/commerce-modules)).

- **Catalogue:** Product Module covers variants/categories; storefront guides cover list/retrieve/variant/price/inventory ([Storefront development](https://docs.medusajs.com/resources/storefront-development)).
- **Carts / checkout:** Cart Module + step-by-step checkout guides (email, address, shipping, payment provider, complete cart, order confirmation).
- **Promotions:** Promotion Module — discounts on items, shipping, or order; rules and campaigns ([Promotion Module](https://docs.medusajs.com/resources/commerce-modules/promotion)).
- **Tax / VAT-inclusive:** Tax Module manages tax regions and rates ([Tax Module](https://docs.medusajs.com/resources/commerce-modules/tax); [Admin tax regions](https://docs.medusajs.com/user-guide/settings/tax-regions)). Pricing Module supports **tax-inclusive pricing** via `PricePreference` (`attribute` `region_id` or `currency_code`, `is_tax_inclusive: true`) ([Tax-inclusive pricing](https://docs.medusajs.com/resources/commerce-modules/pricing/tax-inclusive-pricing)) — suitable for ZAR VAT-inclusive display with a South Africa tax region.
- **Payments:** Official Stripe Module Provider with webhook route pattern `{server_url}/hooks/payment/{provider_id}` ([Stripe provider](https://docs.medusajs.com/resources/commerce-modules/payment/payment-provider/stripe)). Custom payment providers can wrap a South African hosted PSP if Stripe is not the chosen rail (payment fees remain outside the USD 50 platform budget per #716).
- **Customers / orders:** Customer Module supports guest and registered customers ([Customer Module](https://docs.medusajs.com/resources/commerce-modules/customer)). Order Module covers management, draft orders, returns/edits/exchanges/claims ([Order Module](https://docs.medusajs.com/resources/commerce-modules/order)).
- **Auth / passwordless:** Auth Module provides email/password, third-party/social, email verification, MFA, and **custom authentication providers** ([Auth Module](https://docs.medusajs.com/resources/commerce-modules/auth)). V1’s “hosted passwordless, no stored passwords” requirement is met by integrating a hosted IdP (or a custom Auth Module Provider that never persists password hashes) — not by using the default email/password provider for customers.

### Extension and ops SoR boundary

Modules isolate domain logic; workflows provide multi-step flows with compensation/rollback ([Modules fundamentals](https://docs.medusajs.com/learn/fundamentals/modules)). That is the right seam for projecting a catalogue from Vellano (and later Odoo) without making the ops SoR own checkout. Official recipes explicitly cover ERP-style integrations.

### Next.js fit

Storefront is separate from the Medusa server/admin. Official path: `npx create-medusa-app@latest --with-nextjs-starter` (backend in `apps/backend`, storefront in `apps/storefront`); JS SDK for Store API ([Next.js Starter](https://docs.medusajs.com/resources/nextjs-starter); [Storefront development](https://docs.medusajs.com/resources/storefront-development)).

### Production / Railway operational requirements

Official general deployment guide requires ([General deployment](https://docs.medusajs.com/learn/deployment/general)):

1. PostgreSQL  
2. Redis (sessions; production also recommends Redis caching, event bus, workflow engine, locking)  
3. Medusa **server** instance (`MEDUSA_WORKER_MODE=server`) serving Admin  
4. Medusa **worker** instance (`MEDUSA_WORKER_MODE=worker`, Admin disabled) for jobs/subscribers  
5. Production file storage (e.g. S3-compatible File Module Provider)  
6. Hosting with **at least 2 GB RAM** for optimal experience  
7. Secrets: `COOKIE_SECRET`, `JWT_SECRET`; CORS for store/admin/auth  

Railway is compatible in principle (Postgres + Redis plugins, multiple services, object storage). Expect tuning for `HOST`/`PORT` and healthchecks (historical community issues on Railway deployments). Prefer separate server/worker for production; `shared` worker mode exists for constrained environments but is a deliberate trade-off.

### Cost under USD 50

**Option A — Medusa Cloud Develop (fits ceiling cleanly)**  
From [medusajs.com/pricing](https://medusajs.com/pricing): Develop **from USD 29/mo** includes deploy-from-GitHub, **storefront & backend hosting**, cache, emails, PR previews; **no GMV platform fee**. Launch is **from USD 99/mo** (exceeds ceiling). Usage add-ons (previews, seats, compute overages) must be watched so the bill stays ≤ USD 50.

**Option B — Self-host on Railway (fits with discipline)**  
Railway pricing ([railway.com/pricing](https://railway.com/pricing)): Hobby USD 5/mo (includes USD 5 usage) or Pro USD 20/mo (includes USD 20); metered RAM ≈ USD 10/GB-mo, CPU ≈ USD 20/vCPU-mo, volumes ≈ USD 0.15/GB-mo, egress USD 0.05/GB, object storage USD 0.015/GB-mo.

Illustrative lean V1 stack (usage only, before plan fee / included credits):

| Service | Rough resources | Approx. USD/mo |
| --- | --- | --- |
| Medusa server | 1–2 GB RAM, fractional vCPU | 10–25 |
| Medusa worker | 0.5–1 GB RAM | 5–12 |
| PostgreSQL | ~1 GB RAM + volume | 10–12 |
| Redis | 0.25–0.5 GB | 2.5–5 |
| Next.js storefront | 0.5 GB | 5 |
| Object storage | small | &lt;1–5 |
| **Subtotal usage** | | **~33–60** |
| Plan fee net of included credit | Hobby/Pro | 5–20 |

**Conclusion on cost:** Medusa Cloud Develop (~USD 29) is the simplest way to stay under USD 50 with vendor-tuned infra. Railway self-host is viable if services are right-sized (possibly starting with shared worker mode and bumping RAM carefully) and the Next.js storefront shares the same Railway project budget; a “comfortable” 2 GB server + separate worker + Redis + Postgres + storefront can approach or breach USD 50 — treat that as a hard constraint during capacity planning.

Medusa OSS core is MIT-licensed (Enterprise Edition materials separately licensed) ([medusajs/medusa LICENSE](https://github.com/medusajs/medusa/blob/develop/LICENSE)); GitHub lists ~36k stars ([medusajs/medusa](https://github.com/medusajs/medusa)).

## Alternatives (why not for V1)

### Saleor

- Genuine OSS under OSI-approved BSD terms; Cloud ↔ OSS migration supported ([Open Source](https://docs.saleor.io/overview/why-saleor/open-source)).
- Preferred self-host shape: Docker images for API, Celery worker, scheduler, plus dashboard ([Docker images](https://docs.saleor.io/setup/docker-images)) — more moving parts than Medusa on Railway.
- Next.js storefront exists ([Quickstart](https://docs.saleor.io/setup/quickstart)).
- **Cloud Forever Free is non-commercial**; commercial Cloud includes a starter GMV plan (up to USD 200k monthly GMV with 0.8% overage) and **Volume at USD 3999/mo** ([saleor.io/pricing](https://saleor.io/pricing)) — incompatible with the USD 50 platform ceiling unless fully self-hosted.
- Stack (Python/GraphQL) diverges from the F0rge/Next.js TypeScript centre of gravity → higher maintenance for this team.

### Vendure

- TypeScript/NestJS/GraphQL; Core free under GPLv3; Platform is a separate commercial subscription with no GMV fees ([vendure.io/pricing](https://vendure.io/pricing); [vendure.io/core](https://vendure.io/core)).
- **Official Railway deployment guide** (server + worker + Postgres; documents ~USD 5/mo after trial for a minimal sample) ([Deploy to Railway](https://docs.vendure.io/current/core/deployment/deploy-to-railway)).
- Credible runner-up for Railway + TypeScript. Trade-offs vs Medusa: smaller community (~8.5k stars, [vendure-ecommerce/vendure](https://github.com/vendure-ecommerce/vendure)), GraphQL-first storefront work, and GPL obligations if the product is ever distributed as on-prem software (internal SaaS use is generally fine per Vendure’s own GPL guidance, but legal should confirm).

### Commerce Layer

- Hosted-only (“Do you offer an on-premise version? No”) ([commercelayer.io/pricing](https://commercelayer.io/pricing)).
- Developer free: 100 live orders/month; Enterprise custom. Good as a thin commerce API, but V1 would inherit opaque paid pricing and no Railway-owned backend — weaker fit for a replaceable ops SoR and a hard USD 50 ceiling beyond the free order cap.

### Thin custom layer

- Lowest licence/infra cost; highest risk for furniture retail: tax-inclusive totals, promotion stacking, payment capture/idempotency, order edits/returns, and inventory consistency are easy to get wrong.
- Conflicts with the wayfinder intent that **the commerce engine owns commerce workflow concerns** (#716). Reject for V1 unless scope collapses to a brochure site with manual payment.

## Recommendation

**Select Medusa (current v2 line) as the V1 commerce engine.**

**Deployment preference under the USD 50 ceiling:**

1. **Preferred for predictability:** Medusa Cloud **Develop** (from USD 29/mo) for backend + starter storefront hosting, with custom Next.js UI as needed — stays under USD 50 if usage add-ons are controlled.  
2. **Preferred for Railway alignment:** Self-host Medusa on Railway (Postgres + Redis + server [+ worker] + object storage + Next.js storefront), right-sized to keep total ≤ USD 50; accept shared worker mode only as a temporary V1 cost compromise if metering requires it.

**Why Medusa wins for this map:** TypeScript/Next.js alignment; full V1 commerce surface (catalogue, cart, promotions, tax-inclusive pricing, checkout, payments, customers, orders); module/workflow extension for Vellano→later-Odoo projection; MIT OSS with no GMV tax; path to stay under USD 50 via Cloud Develop or lean Railway; explicit storefront separation matching a highly customisable furniture UX.

**Implementation notes for later tickets (not decisions here):**

- Configure a South Africa tax region + ZAR price preference with `is_tax_inclusive: true`.  
- Use a **custom Auth Module Provider** or hosted IdP so customer auth is passwordless and passwords are never stored in Medusa.  
- Integrate hosted payment via Stripe (if SA rails suffice) or a custom Payment Module Provider for the chosen local PSP; PSP fees stay outside the platform budget.  
- Treat Medusa as commerce SoR for cart/checkout/order; sync products/stock/fulfilment events to/from Vellano through workflows — keep the boundary replaceable.

## Invalidation conditions

Revisit this recommendation if any of the following become true:

1. **Budget:** Measured Railway self-host cost for a production-shaped Medusa stack (≈2 GB server + worker + Postgres + Redis + storefront + storage) **cannot** stay ≤ USD 50/month **and** Medusa Cloud Develop (or equivalent ≤ USD 50 managed tier) is unavailable, inadequate for production traffic, or forces paid add-ons that breach the ceiling.  
2. **Auth:** Passwordless hosted auth cannot be integrated through Medusa’s Auth Module Provider / third-party providers without storing password credentials in the commerce DB.  
3. **Payments:** No workable Payment Module Provider path exists for the chosen South African hosted PSP (webhooks, capture, refunds) within V1 timeline.  
4. **Tax:** Tax-inclusive ZAR VAT behaviour cannot be configured correctly for furniture SKUs (e.g. preference/promotion interactions fail compliance review).  
5. **Ops model:** Requirements shift to heavy multi-warehouse / multi-channel B2B where Saleor’s built-in channel/warehouse model is decisively cheaper to operate than Medusa modules — **and** self-hosted Saleor ops capacity exists.  
6. **Licence:** Legal rejects Medusa’s licence split (MIT + Enterprise Edition materials) or, if reconsidering Vendure, rejects GPLv3 for the intended distribution model.  
7. **Scope collapse:** V1 is reduced to content-only with offline payment, making any commerce engine unjustified versus a thin custom form.

## Sources

| Claim area | URL |
| --- | --- |
| Medusa commerce modules list | https://docs.medusajs.com/resources/commerce-modules |
| Medusa deployment (Postgres, Redis, server/worker, 2 GB) | https://docs.medusajs.com/learn/deployment/general |
| Medusa Cloud pricing (Develop USD 29, Launch USD 99, no GMV fee) | https://medusajs.com/pricing |
| Medusa tax-inclusive pricing | https://docs.medusajs.com/resources/commerce-modules/pricing/tax-inclusive-pricing |
| Medusa Tax Module | https://docs.medusajs.com/resources/commerce-modules/tax |
| Medusa Admin tax regions | https://docs.medusajs.com/user-guide/settings/tax-regions |
| Medusa Promotion Module | https://docs.medusajs.com/resources/commerce-modules/promotion |
| Medusa Cart Module | https://docs.medusajs.com/resources/commerce-modules/cart |
| Medusa Order Module | https://docs.medusajs.com/resources/commerce-modules/order |
| Medusa Customer Module | https://docs.medusajs.com/resources/commerce-modules/customer |
| Medusa Auth Module | https://docs.medusajs.com/resources/commerce-modules/auth |
| Medusa Stripe payment provider | https://docs.medusajs.com/resources/commerce-modules/payment/payment-provider/stripe |
| Medusa Pricing Module (tax-inclusive feature list) | https://docs.medusajs.com/resources/commerce-modules/pricing |
| Medusa modules / extension model | https://docs.medusajs.com/learn/fundamentals/modules |
| Medusa Next.js Starter | https://docs.medusajs.com/resources/nextjs-starter |
| Medusa storefront development | https://docs.medusajs.com/resources/storefront-development |
| Medusa GitHub / stars | https://github.com/medusajs/medusa |
| Medusa LICENSE (MIT + EE note) | https://github.com/medusajs/medusa/blob/develop/LICENSE |
| Saleor Cloud pricing | https://saleor.io/pricing |
| Saleor open source / BSD | https://docs.saleor.io/overview/why-saleor/open-source |
| Saleor Docker / worker / scheduler | https://docs.saleor.io/setup/docker-images |
| Saleor quickstart / Next storefront | https://docs.saleor.io/setup/quickstart |
| Saleor GitHub | https://github.com/saleor/saleor |
| Vendure pricing / Core GPLv3 | https://vendure.io/pricing |
| Vendure Core product page | https://vendure.io/core |
| Vendure deploy to Railway | https://docs.vendure.io/current/core/deployment/deploy-to-railway |
| Vendure GitHub | https://github.com/vendure-ecommerce/vendure |
| Commerce Layer pricing (no on-prem; free 100 live orders) | https://commercelayer.io/pricing |
| Railway pricing / plans | https://railway.com/pricing |
| Railway plans docs | https://docs.railway.com/pricing/plans |
| Parent wayfinder #716 | https://github.com/F0rge/f0rge/issues/716 |
| This research issue #717 | https://github.com/F0rge/f0rge/issues/717 |
