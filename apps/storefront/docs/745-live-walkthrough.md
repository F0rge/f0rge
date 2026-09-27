# Issue #745 live walkthrough

This walkthrough was performed against disposable local Firstout, Medusa and
Storefront instances, with separate PostgreSQL databases and Redis. The published
catalogue contained an Arc sofa, an Alba chair and a two-finish Arc group. A
separate wall sconce remained in draft. The catalogue data and locally generated
test images are not launch assets.

## Desktop and mobile

- Home, Collections and Shop linked to published Medusa products. A published
  product opened directly by its source SKU ID; the draft and an unknown ID
  returned the recoverable 404 page.
- Search, category, collection, stock, minimum/maximum price and sorting composed
  on `/shop`. Refresh preserved the selection; clearing filters and browser Back
  restored the earlier URL state. An unmatched query showed the empty state and
  a link back to all pieces.
- The two-finish group switched SKU, price, availability and gallery on variant
  selection. A price filter showed the matching variant's price on its card.
- At a 390px viewport, navigation, filters and gallery remained usable without
  horizontal document overflow. Keyboard focus reached the skip link, search,
  submit button, product link, variant selector and gallery buttons. Enter
  activated the controls and the selected gallery button updated `aria-pressed`.
- With Medusa temporarily stopped, the error page kept site navigation and
  offered a retry. After Medusa restarted, retry restored the catalogue.

## Verification

`storefront-web` Playwright catalogue and discovery specs ran against the live
local stack with all four fixture IDs set. The accessibility assertions inspect
the browser's roles, focus, live status text, and image alternatives; an actual
assistive-technology spoken walkthrough remains a manual release check.
