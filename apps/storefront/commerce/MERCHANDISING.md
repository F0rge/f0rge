# Firstout DasKasas publication

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

Staff choose a piece's category in Medusa Admin:

1. Open **Products** and the piece.
2. Under **Organize**, choose **Edit**, pick one of the four categories, and save.
3. The shop reads categories from Medusa directly. No Firstout change or sync is needed.

The Firstout sync never writes or clears product categories, so a staff choice
stays across syncs. A published piece with no category appears only under
**Shop all**.

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

What the shop does not require, because Firstout does not store it:

- A long description. A short description is shown when one exists.
- A material, care instructions, or dimensions.
- Photos. The product card uses a placeholder when the gallery is empty.

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
