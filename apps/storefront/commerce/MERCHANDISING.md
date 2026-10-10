# Firstout storefront publication

The private Ops snapshot owns product-group membership, option values, source SKU
identity, ZAR retail price, and available stock. Medusa can also store a
description, images, SEO, dimensions, materials, and care instructions when a
merchant has them. Firstout's catalogue does not. The sync creates new products
as drafts, then publishes every in-stock (or finite made-to-order) product into
the **In stock** collection, handle `in-stock`. Each product is published on its
own. A product the publication hook rejects for a missing tax-inclusive ZAR
price stays a draft. The sync does not invent a price, and that rejection does
not roll back the priced products in the same run. A product leaves that
collection and returns to draft when it is no longer in the Ops feed or none of
its variants has positive stock or a live made-to-order offer. Later sync runs update
source-owned variant fields. A group has the stable handle
`firstout-group-<group UUID>`.

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
