# Firstout DasKasas publication

## Reviewed catalogue

When Firstout activates a reviewed catalogue for the shop, it supplies the
curated SKU set through the private Ops product feed. The shop matches stable
Firstout SKU IDs. A source product outside the set returns to draft. A manually
managed Medusa product loses its link to the DasKasas sales channel and keeps
its other channels. A new stock or photo record cannot add a SKU to the curated
set.

Each approved variant carries its own stock, price, centimetre measurements,
piece count and three reviewed studio images. The first image is its hero.
The sync verifies all three image hashes and attaches the files in source
order before publishing the product. Firstout can append a room setting and a
material close-up to a reviewed variant. The shop shows the studio images,
then the setting, then the close-up when present. The setting is served from
slot 4 and the close-up from slot 5. A close-up works without a setting. If a
supplemental image fails to sync, a previously verified studio gallery can
stay published while the sync retries. Variants without a reviewed studio
gallery keep their existing catalogue data. Internal Firstout notes stay in
Firstout.

Each visible product needs a priced, available variant. An out-of-stock
variant in that family remains visible as an option, with purchases disabled.
Adding to a bag or editing a line checks the total requested for that SKU.
Checkout revalidates availability and reserves stock before paying.

Regrouping through Medusa can replace the operational variant and its inventory
links. The curated sync checks for active reservations and unsettled paid or
made-to-order commitments before attempting the move. A paid order also needs
a durable handoff snapshot and a terminal fulfillment status before the
historical variant can be replaced. Run the sync again after the reported
SKU's commitments have cleared.

## Legacy catalogue

The private Ops snapshot owns product-group membership, option values, source SKU
identity, ZAR retail price, and available stock. Medusa can also store a
description, images, SEO, dimensions, materials, and care instructions when a
merchant has them. Firstout's catalogue does not. The sync creates new products
as drafts, then publishes every in-stock (or finite made-to-order) product into
the **On Sale** collection, handle `on-sale`. An existing collection with handle
`in-stock` is renamed in place to that title and handle. The shop's availability
filter stays `in-stock`. Each product is published on its own. A product the
publication hook rejects for a missing tax-inclusive ZAR price stays a draft.
The sync does not invent a price, and that rejection does not roll back the
priced products in the same run. A product leaves On Sale and returns to draft
when it is no longer in the Ops feed or none of its variants has positive stock
or a live made-to-order offer. Publish and withdraw set status and
`collection_id` only, so gallery images and other product metadata stay.

On Sale is the internal publication gate, not a menu item. Shoppers browse by
four Medusa product categories: Sofas & Armchairs (`sofas-armchairs`), Dining
Room (`dining-room`), Bedroom (`bedroom`) and Coffee & Console Tables
(`coffee-console-tables`). The bootstrap creates any that are missing, active
and public, on every release. It never edits a category that already exists.

Which pieces are on the shop, and in which category, comes from Firstout
(owner decision, 21 Nov 2026). With `OPS_COMMERCE_AUTO_PUBLISH_ENABLED=true` on
`firstout-api`, the feed holds every SKU that:

- is in a mapped Firstout category (matched trimmed and in any case):

  | Firstout category | Shop category |
  |---|---|
  | Sofas, Armchairs | `sofas-armchairs` |
  | Dining Room | `dining-room` |
  | Bedroom | `bedroom` |
  | Coffee and Lamp Tables, Consoles and TV Units | `coffee-console-tables` |

- has a Firstout photo, and
- is not switched to **Hide from shop** on its Firstout SKU page.

It also needs to be sellable, unarchived and priced, as before. Only pieces in
stock or with a live made-to-order offer reach On Sale; the rest stay drafts.
This replaces the hand-set Firstout publish flag. The rule applies to every
SKU, grouped or not: a product group shows with only the members that meet it,
and is left out entirely if none does. A group with an archived, unsellable or
unpriced member stays off the shop, as before. If a group's qualifying members
map to different shop categories, the group takes the category of its first
qualifying member by SKU code, so every variant of one product shares one
category. The mapping lives in Firstout (`SHOP_CATEGORIES` in
`apps/firstout/backend/app/crud/ops_commerce.py`), and Firstout's database
matches the category against it.

Each product carries `shop_category`. The sync puts the product in that Medusa
category and takes it out of the other three. It never adds or removes any other
category, so a staff-made category stays. Staff no longer assign the four
categories in Medusa Admin: a change there is put back on the next sync run.
A piece that leaves the feed is withdrawn to draft as before and keeps its
category.

Names and categories are written only for feed rows that carry
`shop_category`. With the Firstout setting off, the sync changes neither.

Names: the sync creates a product with its Firstout name and records that name
in product metadata `firstout_title`. A later Firstout rename updates the title
only while the title still equals `firstout_title`; once staff edit the title in
Medusa Admin, the sync never overwrites it. A product created before names were
recorded is adopted while its title still equals the Firstout name, and is
treated as staff-edited otherwise. Variant titles come from option values, as
before. Names and categories run after the stock sync, outside the inventory
lock; a failure there is logged and retried next run.

Go-live: Firstout sends `shop_category` only when
`OPS_COMMERCE_AUTO_PUBLISH_ENABLED` is on, and it is off by default, because a
commerce release older than this one rejects the unknown key and pauses
checkout. With it off, the feed is selected by the publish flag as before and
the sync leaves categories alone. After both the Firstout and DasKasas releases
are live, set `OPS_COMMERCE_AUTO_PUBLISH_ENABLED=true` on `firstout-api` and
redeploy it. Turning it on also sends `photo_token`, whatever
`OPS_COMMERCE_PHOTO_TOKENS_ENABLED` says. Pieces published by hand that fail the
rule, such as the ones without a photo, drop out of the feed and are withdrawn.
About 300 photos at about 1 MB each fit the 1 GB photo volume.

Rollback: turn `OPS_COMMERCE_AUTO_PUBLISH_ENABLED` off before rolling commerce
back to a pre-#1018 image; that image rejects `shop_category` and pauses
checkout. Turning the setting off returns the feed to the publish flag, so
pieces not published by hand are withdrawn on the next sync.

A published piece with no category appears only under **Shop all**.

The four category names and handles are also written in the web code,
`web/src/lib/shop-categories.ts`, which drives the header, footer, category
pages, sitemap and old-link redirects. Renaming a category, changing its handle
or deactivating it in Admin therefore needs a matching code change. Deleting one
does not stick: the bootstrap recreates a missing category on the next release.

Earlier syncs guessed rooms from titles and SKU prefixes, wrote
`storefront_room_collections` on product metadata, and created the collections
`sofas` and `dining-room`. That guessing is gone. Those collections and the
metadata key stay in the database unused; the shop no longer reads them.
Deleting the two collections needs the owner's approval.

Later sync runs update source-owned variant fields. A group has the stable
handle `firstout-group-<group UUID>`.

What the shop requires before a Firstout product is published:

- A title, SKU, and source SKU id.
- Complete option values projected from Ops.
- A positive tax-inclusive ZAR price. The bootstrap marks ZAR store currency and
  the South Africa region tax inclusive.
- Positive Ops stock, or a finite made-to-order offer with remaining capacity and
  a lead-time window.

What the shop does not require:

- A long description. A short description is shown when one exists. Firstout
  does not store one.
- A material, care instructions, or dimensions. Firstout does not store them.
- Photos. The product card uses a placeholder when the gallery is empty. Photos
  come from Firstout when it has one (below), but a SKU without a photo still
  publishes.

## Selling rules from Firstout

With `include_sell_rules=true` the feed carries `sell_multiple` and
`min_quantity` (positive integers) per SKU. The sync writes them to variant
metadata under the same keys, only when they change. A feed without them (an
older Firstout) leaves the stored values alone; null clears them, and a missing
value means 1. Before payment, the add-to-bag and update-line hooks refuse a
variant total that is not a multiple of `sell_multiple` or is below
`min_quantity`, and the checkout hold turns such a bag into a review. The
purchasable cap is the stock cap rounded down to the multiple. Cart completion
does not check the rules: it runs after payment.

## Photos from Firstout

The version 2 feed uses opt-in query parameters for the supplemental images,
the finish swatch (`include_swatch`) and the selling rules
(`include_sell_rules`).
An older Firstout can omit an unsupported field. DasKasas retains the last
verified asset for that slot when it is still attached. An explicit null
removes that asset. Media updates preserve the curated selection and leave
pricing and stock to their existing sync.

Staff add a SKU's photo in Firstout, not in Medusa Admin. The Ops feed carries a
`photo_token` for each SKU, or null when it has none. A feed without the field
(an older Firstout) means no photo information, and the sync leaves photos alone. After each stock sync, and
outside the inventory lock, the sync downloads a photo only when its token
differs from the variant's `firstout_photo_token` metadata. It stores the JPEG
through the Medusa file module (the `commerce-product-photos` volume on Railway,
served from `/static`), adds it to the product gallery and links it to that
variant. The image carries `firstout_source_sku_id` and `firstout_photo_token`
metadata; that marker is how the sync knows an image is its own. Any image
carrying `metadata.firstout_source_sku_id` is treated as sync-owned, so staff
must not set that key on their own images.

- The photo becomes the variant thumbnail when the variant has none, and the
  product thumbnail when the product has none. A thumbnail staff chose stays.
- The sync never removes or replaces an image without its marker. When a token
  changes it replaces only its own image for that SKU.
- If staff delete a synced image in Admin, it stays deleted until the photo
  changes in Firstout.
- A failed download or attach is logged and retried on the next run. It never
  blocks stock or price. A file Medusa refuses to add to the gallery is deleted
  again. Once a photo is in the gallery, a later failure (linking it to the
  variant, setting its thumbnail) retries with that same image and never
  uploads again.
- A replaced photo's old file stays on the volume. Firstout photos are
  write-once today, so this happens only if Firstout gains a replace action.

Go-live: Firstout sends `photo_token` only when `OPS_COMMERCE_PHOTO_TOKENS_ENABLED`
is on, and it is off by default, because a commerce release older than this sync
rejects the unknown key and pauses checkout. After both the Firstout and DasKasas
releases with photo sync are live, set `OPS_COMMERCE_PHOTO_TOKENS_ENABLED=true` on
the `firstout-api` service (Firstout's own Railway project) and redeploy it. The
next sync run downloads every photo once.

The sync accepts only an `image/jpeg` response of at most 5 MB that starts with
the JPEG signature, and does not follow redirects. Anything else is logged and
retried next run, with nothing uploaded.

If a merchant attests photos, set variant metadata `suitable_image_urls` to a
JSON array of URLs from that product's or variant's Medusa gallery (a JSON array
entered as text in Admin is accepted). There is no minimum count. Private hosts
and signed/query-string URLs are rejected. Local generated demo photos are
accepted only outside production with `STOREFRONT_ALLOW_LOCAL_TEST_IMAGES=true`,
and only from `http://127.0.0.1:3004/demo/`.

The publication workflow rejects a product that fails the required checks above.
The add-to-cart and complete-cart workflow hooks recheck the selected variant
and its sales channel, so calling Medusa's Store API directly does not bypass
the gate.

If option **names** change after a group is projected, sync stops and requires a
manual Medusa option migration. Option values and SKU membership can change. A
group stays published only while every variant still has stock or a live
made-to-order offer.
