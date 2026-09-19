# #723 — Catalogue ownership and fresh onboarding (resolved)

Map: [Wayfinder: Vellano headless storefront replacement](https://github.com/F0rge/f0rge/issues/716)

## Decision

| Concern | Owner |
|---|---|
| Durable product→variant→SKU identity | Vellano (extend minimally: parent + variant SKUs); Medusa mirrors via Ops API |
| Merchandising (titles, rich copy, collections, SEO, publish) | Medusa (display name default from Vellano, overridable) |
| Ops attributes (cost, warehouse, fabric/design codes) | Vellano |
| Storefront images / gallery | Medusa (or its object store); one-shot copy from Cin7/Vellano OK |
| Sellable gate | Explicit Medusa published / sales-channel + synced ATP & price |
| DTC promotions | Medusa (per #724) |
| Cin7 | One-shot export → cleanse → import Vellano → project to Medusa; no ongoing Cin7 dependency |
| V1 import effort | Scripted/manual load of curated launch set only (~30–80 sellable variants) |

## Grilling

Q1–Q8 accepted as recommended (2026-09-19, Leonardo).
