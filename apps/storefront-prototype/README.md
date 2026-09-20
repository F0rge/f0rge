# Vellano storefront design prototype

Throwaway design source for [Prototype the V1 furniture storefront](https://github.com/F0rge/f0rge/issues/720), on `codex/storefront-design-prototype`. It is a visual and interaction reference, not production commerce architecture.

## Run

From the repository root, install the workspace dependencies with `npm ci`, then the prototype's pinned dependencies with `npm ci --prefix apps/storefront-prototype --workspaces=false`.

```sh
npm run dev --prefix apps/storefront-prototype
```

Open <http://127.0.0.1:3015/prototype?variant=D>. The Nx target is `storefront-prototype:dev`.

```sh
npm run build --prefix apps/storefront-prototype
```

## Directions

| Option | Direction     | Character                                                                                                  |
| ------ | ------------- | ---------------------------------------------------------------------------------------------------------- |
| A      | The Editorial | Full room photography, ivory and olive, quiet serif headings.                                              |
| B      | The Atelier   | Split typography and image, furniture presented as an individual object.                                   |
| C      | The Gallery   | Asymmetric photographic triptych and an oversized central statement.                                       |
| D      | The Collector | C's gallery structure with ten interchangeable typography-and-colour skins, plus a bespoke interactive object study. |

Switch using the bottom bar or left/right keys on the home page. The URL retains the option. State is shared across options; switching on the homepage returns to the hero for comparison. The bar is omitted from production builds; the URL option still works.

D is the latest proposal following Leo's request to retain C and explore a less generic alternative. It is not recorded as a final approved design. Its structure, content and interactions are shared by all ten skins; only typography and colour change.

### D's visual language

The preview control above the design switcher selects a skin, and `?variant=D&palette=1` through `?variant=D&palette=10` links directly to one. Palette 1 remains the original Collector treatment.

| Palette | Name | Heading / body type |
| --- | --- | --- |
| 1 | Oxblood / citron | Bodoni Moda / Manrope |
| 2 | Ultramarine / shell | DM Serif Display / Plus Jakarta Sans |
| 3 | Forest / bone | Lora / Inter |
| 4 | Terracotta / chalk | Fraunces / Work Sans |
| 5 | Ink / saffron | Playfair Display / Source Sans 3 |
| 6 | Aubergine / blush | Libre Baskerville / Sora |
| 7 | Cobalt / ice | Prata / Sora |
| 8 | Moss / sand | Newsreader / Manrope |
| 9 | Charcoal / copper | Bodoni Moda / Archivo |
| 10 | Petrol / stone | Libre Caslon Display / Outfit |

Numbered objects, printed catalogue captions, staggered product heights and the full-screen material study provide the shared character beyond the skin.

## Interactive walkthrough

1. Explore a hero piece, or open the furniture catalogue. Search, filter by category/stock/budget, and sort by price.
2. Select a finish on a product, view dimensions, enlarge the image, save it, and add a quantity to the bag. Unavailable items cannot be added.
3. Change quantities in the bag and enter guest checkout. **Use example details** supplies fictional data. Delivery adds an illustrative R650; collection is complimentary.
4. Review details, open the simulated Peach step and simulate payment. The confirmation explicitly states that no payment or email occurred.
5. Preview passwordless sign-in with `alex@example.com`. The matching simulated order appears in account history. Add/edit an address; it survives page navigation during this preview session and prefills a later checkout.
6. In D, use **A closer look** to enter the Sola study. Scroll to rotate the chair, choose a finish, and reveal the frame by lifting the cushions. Chapter buttons and the slider also control the view. **Pause motion** switches to a compact manual view. OS reduced-motion preferences enable this mode automatically.

All carts, identities, addresses, orders, newsletter actions and consent choices live only in memory. Refreshing resets them. No actual account, email, transaction, analytics event or subscription is created. Images, furniture descriptions, prices, stock, VAT calculations and delivery promises are illustrative. A real store needs verified product data and reviewed policies.

### 3D implementation

The Sola chair is an original procedural Three.js design study, not a model of a real stocked SKU. Timber members, cushions, piping, joints and fabric/wood textures are generated in code. It links to the seating collection rather than claiming it is available for purchase.

Three.js loads only when the study approaches the viewport. Rendering happens on scroll, resize or finish changes rather than a permanent animation loop. Pixel ratio is capped, resources are disposed on unmount, reduced motion has manual controls, and a drawn fallback is provided when WebGL cannot initialise. No scroll interception or custom wheel handler is used.

## Review fixes in this iteration

- Reset the shared dialog's individual CSS `translate` before applying custom positioning; drawers and centred dialogs were otherwise shifted partly off-screen.
- Keep account addresses in session state, scope orders/addresses to the preview identity, and keep checkout mounted when a customer signs in mid-checkout.
- Require sign-in to display an account and prefill the checkout email when identity changes.
- Validate route/article parameters and give missing products an explicit recovery screen.
- Remove duplicate product-gallery images and describe secondary lifestyle images as room inspiration.
- Keep mobile privacy links visible; keep D's palette on portalled dialogs as well as the page.
- Remove machine-specific filesystem paths and pin prototype dependencies in a local lockfile.
- Clear stale section anchors during navigation and make singular item counts read naturally.
- Keep the mobile 3D silhouette clear of narrative and finish controls; cap the open ends of the model's armrests.

## Validation

The design was exercised in a live local browser at desktop and mobile sizes: option switching, all ten D skins, scroll-driven rotation, finish selection, construction reveal, search and empty results, stock filtering, unavailable products, bag quantities, delivery/collection totals, guest checkout, simulated payment, passwordless preview, order history and address continuity. TypeScript and the production build are also checked.

This does not establish production payment, authentication, inventory, accessibility or analytics correctness. Vite reports large chunks for the shared UI and the separately loaded 3D module; production implementation should budget and optimise these assets.

## Analytics handoff

Retain the [storefront analytics decision](https://github.com/F0rge/f0rge/issues/728) when implementing this design. The prototype intentionally sends no telemetry. Production instrumentation should cover page/product visitors, active visible product time, search/filter outcomes, item and finish clicks, saves, cart/checkout steps and purchases. D adds useful interaction points: object-study entry, progress milestones and 3D finish selection. Use catalogue identifiers and coarse interaction properties, never checkout fields or email addresses; follow the consent and exclusion rules in the analytics decision.

## Image sources

The photographic placeholders reuse the repository's existing Unsplash demo assets. The source catalogue is [`apps/vellano/backend/data/playground_photos/SOURCES.md`](../vellano/backend/data/playground_photos/SOURCES.md). The files used here are `bi-sofa-06`, `modular-cloud`, `club-chair`, `london-3s`, `marble-coffee`, `outdoor-teak`, `bi-dining-01`, `walnut-lounge`, `bi-lamp-01` and `sand-modular`. These are visual placeholders, not evidence of actual products or finishes.
