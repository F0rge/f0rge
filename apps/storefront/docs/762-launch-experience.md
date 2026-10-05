# Launch experience preparation

Issue #762 asks for a public-ready Collector experience: an approved catalogue load, reviewed policies, the selected D palette, accessibility and performance evidence, and correct indexing. This change adds that software. It does not supply the owner pack, and it does not turn public selling on.

`loadApprovedLaunchPack` in `apps/storefront/commerce/src/launch-load.ts` is the load. It publishes variants only when `assessLaunchPack` accepts the pack. An incomplete record is left unpublished, and `directPurchase` refuses it. A second load upserts by SKU under `launch:{group}:{sku}` and does not copy over paid order lines. A rejected file leaves the last accepted shelf as it was. `public_selling` is always false.

No owner pack is in the repository. The fictional pack inside `launch-load.test.ts` only proves the loader. Do not pass that file to the script.

## Repeatable check

From `apps/storefront/commerce`:

```bash
npx ts-node --swc -O '{"module":"commonjs"}' src/scripts/load-launch-pack.ts
```

With no file, the command exits 1. The printed summary has `loaded: false`, `public_selling: false`, `published_variants: 0`, and the launch-pack findings. It does not print secrets and it does not write products or orders.

When the owner later provides a pack file outside git:

```bash
npx ts-node --swc -O '{"module":"commonjs"}' src/scripts/load-launch-pack.ts /path/to/launch-pack.json
```

A ready file prints the published count and still sets `public_selling` to false. Applying those mappings to Medusa is a separate operator step. This script does not open a database and does not overwrite paid-order history.

## Customer pages

Support, delivery and collection, returns and refunds, and privacy are linked from the footer and from the analytics panel (`/policies/privacy`) before a visitor can accept analytics. Until a reviewed document is supplied, each page says `Reviewed text for this page is not published.` and does not invent legal, delivery, or refund copy. Made-to-order versus bespoke appears only when that sentence is in the owner text.

The storefront still uses the existing oxblood / citron tokens. `collectorSkinAttribute` applies that skin only when the pack names `Oxblood / citron`. The other nine named skins have no approved colour values here, so they are not applied and there is no theme switch. Retired placeholder lines ("taking shape", "a considered addition to your living space") are not rendered.

## Indexing and a future hostname

Catalogue URLs stay non-indexable unless all of these are true: `STOREFRONT_INDEXING_ENABLED=true`, `RAILWAY_ENVIRONMENT_NAME=production`, `STOREFRONT_PRIVATE_PREVIEW=off`, and `NEXT_PUBLIC_BASE_URL` is an `https` origin. This change sets none of those. Account, checkout, bag, sign-in, order confirmation, study, and API routes stay `noindex` even then. `robots.txt` disallows `/` while indexing is off. The sitemap lists home, shop, collections, support, policies, product paths, and collection filters only when indexing is on.

No public hostname has been chosen. When the owner authorizes one, set `NEXT_PUBLIC_BASE_URL` to that origin. Do not buy a domain as part of this preparation.

## Accessibility and performance

Purchase failures on the bag, product, and checkout pages use a focusable `role="alert"`. The collection error heading takes focus when the catalogue cannot load. Text pairs in the current oxblood / citron palette measure above WCAG AA 4.5:1 (ink on paper 11.22, paper on oxblood 9.59, citron on oxblood 7.68, muted on paper 4.69, ink on citron 8.98).

The first hero image and the product gallery image request high priority and reserve a 4:5 box. Median LCP, CLS, and field INP were not measured: there is no approved image pack, so those numbers are not invented. Hosted Clerk sign-in and Peach checkout were not exercised: those credentials are not in this environment.

## Rollback

If a pack file fails validation, leave indexing disabled and leave the private preview gate on. Do not add a live Peach key and do not start new payment attempts. Redeploy the last verified git release. Do not restore by overwriting paid-order tables or integration state. The loader's rejected path does not change the shelf it was given.

## Still open

#762 stays open. The owner still has to supply the approved catalogue, policies, palette choice, and provisioning. #758 is also still open. A live discovery-to-confirmation walkthrough with that catalogue, measured LCP/CLS, and hosted auth or payment is not possible until those inputs exist.
