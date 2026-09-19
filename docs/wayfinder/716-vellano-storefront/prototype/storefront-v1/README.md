# PROTOTYPE — Vellano storefront V1 UI (#720)

> **Throwaway.** Answers a look-and-feel question. Not production architecture.  
> Branch: `prototype/vellano-storefront-ui`  
> Map: [Wayfinder #716](https://github.com/F0rge/f0rge/issues/716) · Ticket: [#720](https://github.com/F0rge/f0rge/issues/720)

## Question

What should the greenfield furniture Storefront look and feel like across catalogue/search, product detail with SKU variants, cart, guest checkout, optional passwordless account, order history, and saved addresses?

Informed by **Medusa DTC Starter** flow patterns (catalogue → PDP/variants → cart → multi-step checkout → accounts/orders), brand-customisable. Static mock only — Peach, soft hold, Clerk magic-link are stubs.

## Plan

Three radically different UI variants on one static app, switchable via `?v=` + floating bottom bar:

| `?v=` | Name | Structural idea |
|-------|------|-----------------|
| `editorial` (default) | Editorial gallery | Magazine hero, horizontal collection rails, split PDP narrative |
| `scandi` | Minimal Scandinavian | Dominant search, left filter rail, list-cards, stepper checkout |
| `industrial` | Bold industrial | Dark / mono, price-first SKU table, sticky buy + cart dock |

Shared flows (same state machine): home/catalogue+search · PDP fabric/size · cart · guest checkout (showroom + domestic shipping, soft hold, Peach mock) · magic-link account · order history · saved addresses.

## How to run

From this directory:

```bash
cd docs/wayfinder/716-vellano-storefront/prototype/storefront-v1
python3 -m http.server 8765
```

Or:

```bash
npx --yes serve -p 8765
```

Open:

- http://localhost:8765/?v=editorial
- http://localhost:8765/?v=scandi
- http://localhost:8765/?v=industrial

Keyboard: `←` / `→` cycles variants (ignored while typing in inputs).

## What to review (Leonardo)

1. **Which information hierarchy wins for furniture?** Editorial storytelling vs scandi browse density vs industrial SKU table.
2. **PDP variants** — chip radios OK for fabric/size, or do we need swatches / size guide more prominently?
3. **Guest checkout first** — is the soft-hold callout clear enough before Peach?
4. **Shipping** — showroom collect vs Gauteng vs national: enough for V1, or need more provinces?
5. **Account optional** — magic-link as post-purchase / side door, or prompt earlier?
6. **Steal bits** — e.g. industrial cart dock + editorial PDP + scandi stepper?

State panel (top-right) shows cart / user / checkout snapshot after every action. No persistence — refresh resets.

## Out of scope

- Real Medusa / Peach / Clerk wiring  
- Production Vellano app routes  
- Closing GitHub #720 (human review first)
