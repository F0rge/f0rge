# Firstout storefront publication

The private Ops snapshot owns product-group membership, option values, source SKU
identity, ZAR retail price, and available stock. Medusa owns product descriptions,
images, collections, SEO, dimensions, materials, care instructions, and publication.
The sync creates new products as drafts and updates only source-owned variant fields
on later runs. A group has the stable handle `firstout-group-<group UUID>`.

Before publishing a Firstout product in Medusa Admin, complete every variant:

- Give the product a useful description (at least 80 characters).
- Set a material on the product or variant.
- Set positive length, width, and height on the product or variant, and set product
  metadata `dimension_unit` to `cm` or `mm`.
- Set product metadata `care_instructions` to useful care text (at least 15 characters).
- Production publication requires at least three distinct public HTTPS photos
  suitable for each finish.
  For **each variant**, set metadata `suitable_image_urls` to a JSON array of at
  least three photo URLs from that product's or variant's Medusa gallery (a JSON
  array entered as text in Admin is accepted). This is the
  merchant's explicit suitability attestation; a shared gallery does not
  automatically count for every finish. Private hosts and signed/query-string
  URLs are rejected. Local generated demo photos are accepted only outside
  production with `STOREFRONT_ALLOW_LOCAL_TEST_IMAGES=true`, and only from
  `http://127.0.0.1:3004/demo/`.
- Ensure the Ops retail price is positive and tax inclusive. The bootstrap marks
  ZAR store currency and South Africa region tax inclusive.
- Ensure the Ops stock is positive, or set variant metadata `lead_time_days` to a
  positive number for made-to-order items (numeric text in Admin is accepted).

Each variant must have the source SKU identity and complete option values projected
from Ops. The publication workflow rejects incomplete products. The add-to-cart and
complete-cart workflow hooks recheck the selected variant and its sales channel, so
calling Medusa's Store API directly does not bypass the gate.

If option **names** change after a group is projected, sync stops and requires a
manual Medusa option migration. Option values and SKU membership can change;
membership changes return an already published product to draft for review.
