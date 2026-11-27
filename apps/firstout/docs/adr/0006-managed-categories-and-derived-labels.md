---
status: accepted
date: 2026-11-26
decided-by: Leo
---

# Managed categories, with the old category and fabric columns kept as read models

A SKU's category used to be free text (`skus.category`), and ledger posting (`category_account_maps`) and the shop section (`SHOP_CATEGORIES`) both matched on that name, so a typo or a rename silently moved a SKU's sales to the 4000 fallback or off the shop. Leo asked for categories with sub-categories and for materials and a colour name in place of the typed Fabric field.

- **Categories and materials are rows staff maintain** (`sku_categories`, two levels; `materials`, with a family). A SKU points at them by id. The shop section is a column on the top-level category row (`shop_category`), so renaming a category keeps its SKUs in the same section.
- **Nothing creates a category or material implicitly.** Only Settings (the list APIs), the migration's backfill and new-tenant signup do. Every other path, including the deprecated `category` name input, CSV import, document intake and the curated import, refuses an unknown name or leaves it empty.
- **`skus.category` stays** as a read model that always equals the top-level category's name. Ledger posting, reports, stocktakes and the workspace filter keep reading the string, and `category_account_maps` stays keyed by name; a rename updates both in the same transaction.
- **`skus.fabric` stays, not null,** as a finish label derived from colour name and main material. Nobody types it, but the `(design, fabric)` unique, purchase order documents, document-intake matching and history still read it.

## Considered options

- **Move ledger posting and every consumer onto `category_id` and drop `skus.category`.** Cleaner, but it rewrites the posting path, reports and the stocktake filter in the same release as the data change. Deferred: the read model makes that a later, separate change.
- **Drop `skus.fabric`** and key uniqueness on design, colour and material ids. Rejected for now for the same reason, and because historical documents print the label.
- **Create a category row on first use** of a new name in SKU create or CSV import, as free text effectively did. Rejected: that is how the list drifts.

## Consequences

- Two sources must agree: services keep `skus.category` in step with `category_id` on every write and rename. A direct database write that changes one without the other breaks posting by name.
- Tests and fixtures must create the categories they name first.
- Dropping either column later needs its own migration and a release-order note; nothing in this decision blocks it.
