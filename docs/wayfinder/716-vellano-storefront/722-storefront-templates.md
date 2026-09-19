# #722 — Survey free React furniture storefront templates

**Map:** [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)  
**Ticket:** [Survey free React furniture storefront templates](https://github.com/F0rge/f0rge/issues/722)  
**Surveyed:** 2026-09-19 (CEST)  
**Method:** Primary sources only (GitHub repo metadata, `package.json` / `LICENSE`, official Medusa docs, live HTTP checks of demos).

## Resolution

**Yes — one template clears the bar for a Medusa-oriented Vellano prototype: the official Medusa DTC Starter storefront (`medusajs/dtc-starter`).** It is MIT-licensed with commercial-use rights, actively maintained (pushed 2026-09-19), on Next.js 15.5 / React 19, and ships responsive catalogue, product-detail (variants), cart, multi-step checkout, and customer accounts wired to Medusa via `@medusajs/js-sdk`. It is not furniture-branded; treat it as a commerce skeleton to restyle with Tailwind, not a finished premium look.

**No furniture-specific free Next.js template cleared the same bar.** Portfolio demos (Luxe, Kosi, Nova) either lack a SPDX `LICENSE` file, are single-maintainer / zero-star, use mock data, or couple to non-Medusa stacks. Saleor’s Paper storefront is modern (Next 16 / React 19) but FSL-1.1-ALv2 and Saleor-coupled. Vercel Commerce is an excellent MIT UI/perf reference but is Shopify-maintained only. The old `medusajs/vercel-commerce` fork last pushed 2023-09 and its listed demo returns 404.

**Recommendation for the prototype:** scaffold from **Medusa DTC Starter `apps/storefront`**, restyle for premium furniture, and borrow *visual* cues from furniture demos without copying their code. Do **not** start from furniture portfolio repos or from primitives alone — DTC already is the maintained Medusa primitive layer (SDK, cart, checkout). Only fall back to a greenfield App Router + Medusa JS SDK if DTC’s UI proves harder to restyle than rewrite.

## Evaluation criteria (from ticket)

| Criterion | How applied |
|-----------|-------------|
| Licence / commercial use | Prefer OSI MIT/Apache with a real `LICENSE` file; reject missing SPDX or FSL competing-use ambiguity for reuse into a Medusa app |
| React 19 + modern Next | Prefer Next ≥15 App Router + React 19 in `package.json` |
| Accessibility | Note declared a11y / Headless UI / Radix use; none of the surveyed templates claim WCAG certification |
| Catalogue / PDP / cart | Require listing, product detail with variants, and cart (checkout preferred) |
| Styling flexibility | Prefer Tailwind / tokenised CSS |
| Dependency health | Recent pushes, official packages, not abandoned forks |
| Backend coupling | Prefer Medusa-native or headless-swappable; penalise Shopify/Saleor/Prisma monoliths |
| Premium furniture fit | Visual suitability *or* clear path to restyle |

## Ranked shortlist

### 1. Medusa DTC Starter storefront — **adopt**

| | |
|--|--|
| **Repo** | https://github.com/medusajs/dtc-starter |
| **Demo** | Live public preview of the (legacy path still hosted) Next starter: https://next.medusajs.com/us (HTTP 200 on 2026-09-19). Local storefront: `http://localhost:8000` per README. Docs: https://docs.medusajs.com/resources/nextjs-starter |
| **Licence** | MIT ([`LICENSE`](https://github.com/medusajs/dtc-starter/blob/main/LICENSE)) — commercial use, modification, redistribution allowed with copyright notice |
| **Stack** | Storefront `package.json`: `next@15.5.24`, `react@19.0.5`, Tailwind 3, Headless UI, Radix accordion, `@medusajs/js-sdk@2.21.0` |
| **Maintained** | GitHub API: `pushed_at` 2026-09-19T06:12:31Z; not archived; MIT SPDX |
| **Patterns** | Product catalog + variants, cart + promotions, multi-step checkout (shipping/payment), accounts, order history, multi-region ([README features](https://github.com/medusajs/dtc-starter/blob/main/README.md)) |
| **Styling** | Tailwind — restylable for a premium furniture brand |
| **Backend** | Tightly coupled to Medusa (desired if Medusa is the engine). Install via `npx create-medusa-app@latest --with-nextjs-starter` or copy `apps/storefront` from this repo ([docs](https://docs.medusajs.com/resources/nextjs-starter)) |
| **a11y** | Uses Headless UI / Radix primitives; no first-party WCAG claim found in docs/README |
| **Furniture fit** | Generic DTC look; suitable as scaffold, not as final brand |

**Why #1:** Only candidate that is free, MIT, React 19 / Next 15, maintained, and Medusa-native with full storefront flows.

### 2. Vercel Next.js Commerce — **reference UI / patterns only**

| | |
|--|--|
| **Repo** | https://github.com/vercel/commerce |
| **Demo** | https://demo.vercel.store (HTTP 200) |
| **Licence** | MIT ([`license.md`](https://github.com/vercel/commerce/blob/main/license.md), Copyright 2025 Vercel, Inc.) |
| **Stack** | `next@15.6.0-canary.60`, `react@19.0.0`, Tailwind 4, Headless UI ([`package.json`](https://github.com/vercel/commerce/blob/main/package.json)) |
| **Maintained** | Active; Vercel states it only actively maintains the **Shopify** provider ([README](https://github.com/vercel/commerce/blob/main/README.md)) |
| **Medusa fit** | Official Medusa fork https://github.com/medusajs/vercel-commerce last `pushed_at` **2023-09-05**; listed demo https://medusa-nextjs-commerce.vercel.app returned **404** on 2026-09-19. Not a safe reuse base. |
| **Verdict** | Excellent MIT catalogue/cart UX and RSC patterns to *study*; do not adopt as Medusa storefront without a full `lib/shopify` rewrite. |

### 3. NextFaster — **perf / architecture reference**

| | |
|--|--|
| **Repo** | https://github.com/ethanniser/NextFaster |
| **Demo** | https://next-faster.vercel.app (HTTP 200) |
| **Licence** | MIT (GitHub SPDX) |
| **Stack** | Next 15 canary, React 19 RC, Drizzle, Neon, Vercel Blob ([`package.json`](https://github.com/ethanniser/NextFaster/blob/main/package.json)) |
| **Coupling** | Own Postgres-backed app — not a headless Medusa client |
| **Verdict** | Strong performance teaching template (~4.8k★); wrong data layer for Vellano. |

### 4. Saleor Paper storefront — **reject for this map**

| | |
|--|--|
| **Repo** | https://github.com/saleor/storefront |
| **Demo** | https://storefront.saleor.io → redirects `/en/default` (HTTP 308) |
| **Licence** | **FSL-1.1-ALv2** ([LICENSE](https://github.com/saleor/storefront/blob/main/LICENSE); [FSL text](https://fsl.software/FSL-1.1-ALv2.template.md)) — permits running a storefront for your business, but forbids Competing Use (commercial products that substitute for Saleor). Not MIT; awkward if code is lifted into a Medusa app. |
| **Stack** | Next 16.3 / React 19.2 ([`package.json`](https://github.com/saleor/storefront/blob/main/package.json)) — technically excellent |
| **Coupling** | Saleor GraphQL — not Medusa |
| **Verdict** | Wrong engine + non-MIT licence for a Medusa-benchmark map. |

## Furniture-themed free demos (moodboard only)

| Project | Demo | Licence evidence | Why it fails the bar |
|---------|------|------------------|----------------------|
| [vikash0p/luxe-furniture-ecommerce](https://github.com/vikash0p/luxe-furniture-ecommerce) | https://luxe-furniture-ecommerce.vercel.app (HTTP 200) | GitHub `license: null`; `LICENSE` file **404**; README claims MIT without SPDX file | Unsafe commercial reuse; 2★; not Medusa |
| [shamimthedev/kosi-furniture-store](https://github.com/shamimthedev/kosi-furniture-store) | https://kosii.vercel.app / README also cites kosi-furniture.vercel.app | GitHub `license: null`; `LICENSE` file **404** | Portfolio / mocked checkout; no SPDX; 0★ |
| [bebshardost/nova-furnishings](https://github.com/bebshardost/nova-furnishings) | https://nova-furnishings.vercel.app | MIT SPDX present | 0★; mock data + BD payments; React 19 / Next 15 per README but not Medusa-coupled; not a maintained commercial template |

Use these only as **visual references** for a premium furniture look after scaffolding DTC.

## Also considered / discarded

| Candidate | Why discarded |
|-----------|---------------|
| [medusajs/nextjs-starter-medusa](https://github.com/medusajs/nextjs-starter-medusa) | **Archived / deprecated**; docs redirect to DTC Starter |
| [slowfound/next-prisma-tailwind-ecommerce](https://github.com/slowfound/next-prisma-tailwind-ecommerce) | MIT, but Next 14 / Prisma monolith; last push 2025-01-01; not Medusa |
| Theme marketplace “free” UI kits | Not surveyed as primary OSS; typically non-commercial or paid licences |

## Accessibility note

None of the shortlisted repos publish a WCAG audit in their primary docs. DTC and Vercel Commerce rely on Headless UI / similar primitives, which is a better starting point than raw `<div>` portfolio UIs, but **a11y for a South African retail launch still needs an explicit ticket** (keyboard, focus, announcements, contrast) after scaffold choice.

## Decision gist (for map index)

Adopt **Medusa DTC Starter storefront** as the free, MIT, React 19 / Next 15 base; restyle for furniture. Treat Vercel Commerce / NextFaster as pattern references. Reject furniture portfolio templates and Saleor Paper as production bases.

## Key sources

1. https://github.com/medusajs/dtc-starter — repo, LICENSE, README, `apps/storefront/package.json`
2. https://docs.medusajs.com/resources/nextjs-starter — official install / deprecation of standalone starter
3. https://github.com/vercel/commerce — README (Shopify-only maintenance), `package.json`, `license.md`
4. https://github.com/medusajs/vercel-commerce — stale Medusa Commerce fork (`pushed_at` 2023-09-05); demo 404
5. https://github.com/ethanniser/NextFaster — MIT perf template + `package.json`
6. https://github.com/saleor/storefront — FSL-1.1-ALv2 + Next 16 / React 19 `package.json`
7. https://fsl.software/FSL-1.1-ALv2.template.md — Competing Use definition
8. Live demos checked 2026-09-19 CEST: `next.medusajs.com/us`, `demo.vercel.store`, `next-faster.vercel.app`, `luxe-furniture-ecommerce.vercel.app`, `storefront.saleor.io`, `medusa-nextjs-commerce.vercel.app`
9. Furniture repos: GitHub API licence fields + LICENSE 404s for Luxe/Kosi; Nova MIT SPDX
