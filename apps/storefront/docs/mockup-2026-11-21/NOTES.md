# DasKasas shop (built from free shadcn-ui-blocks.com blocks)

Vite + React 19 + TS + Tailwind v4 + shadcn/ui. `npm run build` writes `dist/` and
`dist/artifact.html` (the published fragment).

## Data
`src/content.ts` holds every fact: `SHOWROOM_ADDRESS` (the one place to fix the address;
Google says GL15, the Bedford Centre directory says LG15), `showroom` (hours, phones, email),
`pieces` (the six catalogue pieces: SKU, price incl. VAT, stock, room, details from the name),
`arc` (photographed demo piece, price on request, enquiry only), `listings`, `policy`, `faqs`,
`footer`. Prices go through `formatPrice` (`en-ZA`, ZAR).

## Routes (`src/lib/router.tsx`)
`#home #shop #sofas #dining-room #on-sale #arc #bag #checkout #help`, product pages
`#p-<sku lower-case>`. Aliases: `#delivery` → help, `#blocks` → home. A section suffix scrolls
to an id: `#help/contact`, `#help/returns`, `#home/visit`.

## Pages
- `home.tsx`: large-image-split, three-column-preview, featured-list, image-aside,
  cta-sections/quick-contact-cta (Visit the showroom), faq center-aligned.
- `listing.tsx` (shop, sofas, dining-room, on-sale): simple-banner, filter-demo (+ filter-drawer
  below lg, sort select), grid-list, scrolling-preview.
- `product.tsx` (#p-<sku>): gallery-overview, shipping-returns/with-icons,
  trust-guarantee/checklist, cross-sells/simple-grid.
- `arc.tsx`: gallery-overview, feature-tabs-navigation, split-image-features, with-icons,
  checklist, bundle-upsells/side-by-side, simple-grid.
- `bag.tsx`: modern-cart, cross-sells/stacked-list, trust-guarantee/icon-list.
- `checkout.tsx`: Original checkout form (`src/components/checkout-form.tsx`) + compact-cart.
- `help.tsx`: shipping-returns/split-columns, shipping-returns/accordion,
  contact-sections/split-with-details.
- Shell (`App.tsx`): announcement simple-centered, Original navbar, footers/muti-column,
  shopping-cart/sidebar-cart (bag drawer).

`<Block>` is a plain passthrough that records which block a section is.
Bag (`src/lib/bag.tsx`): lines `{ sku, qty }`, capped at stock, starts empty.
