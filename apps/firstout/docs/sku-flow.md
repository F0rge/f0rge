# SKU flow

One SKU surface, reachable from any staff page: a panel that docks beside the
page and expands in place to a full SKU view where every stored field is edited
card by card. Built from the clickable mockup Leo approved on 26 November 2026
(mockup C), with his changes: no colour family, no Fabric field, categories with
sub-categories, and selling rules honoured by the DasKasas shop. It replaces the
catalogue split view and edit modal described in
[`catalogue-explorer.md`](catalogue-explorer.md). API detail lives in
[`AGENTS.md`](../AGENTS.md) (S3, V2-S8, V2-S12, V2-S13, S5); decisions in
[ADR 0005](adr/0005-sale-quantity-rule.md) and
[ADR 0006](adr/0006-managed-categories-and-derived-labels.md).

## Panel and full view

| Surface | Behaviour |
| --- | --- |
| Docked panel | A sibling of `<main>` in the app shell, 28rem wide on the right; `main` gets a right inset so the page stays usable. Below 672px it is a full-width sheet. Sections are collapsible groups with a one-line summary; Overview and Stock start open, and open state survives stepping. |
| Full view | The same element grows to cover the content area: same header, same section order. Overview becomes a sticky facts column with the large photo and barcode; the other sections are cards. The page underneath stays mounted and is `inert`. |
| Header search | `/` or Ctrl/Cmd+K. Rich SKU rows (photo, name, Kit tag, ref and category, available, retail), then purchase orders and invoices, and Administration destinations on Administration pages. A live preview of the highlighted SKU sits on the right (hidden at 800px and below). `Enter` on a SKU docks the panel on the current page with every SKU hit as the stepping context; other hits navigate as before. |
| `SkuLink` | A SKU ref rendered as a real link to `/catalogue/{id}` (new tab and middle click work); a plain click docks the panel. Used on receive, transit, picks (list, detail, matrix), stock by bin, supplier price history, purchase order lines and inside the panel. |
| Catalogue | `RecordWorkspace` without a details pane (`openRecord`): the table is full width and opening a row docks the panel with the current page of rows as context. Paging, sorting and filtering refresh that context. Filters add Sub-category, Material (main or other), Material family and Do not reorder; Category options come from the managed list. Import, DasKasas import, Export CSV (now with sub-category, colour, materials, order up to, do not reorder and the selling rule), New SKU, label printing and archive/restore are kept. |

Keyboard while the panel is open: `↑` `↓` step through the context (no wrap),
`Enter` expands (docked panel focused), `Esc` goes back one level (full → docked
→ closed). Keys are left alone while focus is in an input, select, textarea,
combobox, grid, dialog or similar, or a Carbon modal is open. Closing returns
focus to where it was. Motion is 200 ms on Carbon's productive curve and is off
under `prefers-reduced-motion`.

## URL parameters

| Parameter | Effect |
| --- | --- |
| `?sku=<id>` | Docks the panel on the current page. |
| `&skuView=full` | Expands it to the full view. |
| `/catalogue/{id}` | Deep link: opens the catalogue with that SKU in the full view. |
| `/purchase-orders?new=1&sku=<id>` | Opens the composer with one line for that SKU, its preferred supplier selected when active. |
| `/adjustments?sku=<id>` | Preselects that SKU for a new or open adjustment. |
| `/ledger?posting=1` | Opens Category posting (linked from unmapped categories). |

The panel parameters change with `router.replace`, so the page's own route and
state are untouched and `Esc` returns to them exactly. The stepping context (an
ordered list of SKU ids and a label such as `PO-0142` or `Catalogue`) lives in
`SkuPanelProvider`, not the URL. `RecordWorkspace` keeps the parameters when it
writes its own; another page that rebuilds its query string must wrap it in
`withSkuPanelParams`. The two prefill routes share `sku` with the panel, so the
panel docks on them too.

## Sections

All sections read one response, `GET /api/v1/skus/{id}/overview`, plus small
extra reads (Supply: observed lead times; Shop: the category list; Kit: the
recipe).

| Section | Shows |
| --- | --- |
| Overview | Ref, barcode, name, design; Category › Sub-category; colour name with swatch; main and other materials; dimensions, pieces, cartons, notes; Sellable, Do not reorder; status tags. |
| Stock | On hand by location with bins, Held (with its sales orders and laybys), Available, On order, next arrival. Unit cost with `stock.cost.view`. Read-only: stock changes through receiving, transfers and adjustments. |
| Pricing | The four tier prices with the invoice price preview; Sold in multiples of and Minimum quantity, with the "Customers see" line; Earns commission. |
| Supply | Preferred supplier, supplier ref, planned and observed lead time, reorder minimum, order up to, made-to-order allowance; supplier price rows with minimum order and pack multiple. Prices only with `stock.cost.view`. |
| Shop | Readiness (photo, category has a shop section, retail price, dimensions; dimensions is advisory, the feed does not require it), Hide from shop, every photo slot the SKU has. |
| Kit | The recipe for a kit, or the kits this SKU is used in. |
| Activity | The 15 newest cost-audit events: source, location, date, note, and cost with `stock.cost.view`. |

Archived SKUs show the archived notice and are read-only. Edit controls appear
only with `catalogue.mutate`.

## Editing

> **Re-check against the code.** Written from the build spec (SPEC 6.4) while
> the editing work was still in progress; confirm each point once it lands.

- Each card has Edit; Edit turns that card's fields into inputs with Save and
  Cancel. One card at a time. Leaving a card with changes shows an inline
  "Discard changes to …?" bar.
- Saves go through the real endpoints (`PATCH /skus/{id}`,
  `PUT /skus/{id}/supplier-prices`, `PUT /skus/{id}/bom`, the photo upload)
  and refresh the overview, catalogue and SKU queries. Server 422 field errors
  map onto their fields.
- Overview: Category then Sub-category (each category option names the sales
  account it posts to, or flags the 4000 fallback); colour name with the swatch
  picker; main material grouped by family and other materials as removable
  tags; `Manage categories` and `Manage materials` link to Settings.
- Pricing: the minimum follows the multiple until edited.
- Shop: the first-photo upload where the backend allows it. No controls to
  replace a photo or add other slots.
- Header quick actions: Edit price (opens the Pricing card in edit mode), Print
  label, Add to purchase order (`/purchase-orders?new=1&sku=`), Adjust stock
  (`/adjustments?sku=`).
- The New SKU page uses the same pickers and rules and has no Fabric field.
- The `CatalogueSkuEditor` modal is removed and `/catalogue/{id}` redirects to
  the catalogue with the SKU in the full view, with everything the old page
  offered (identity, cartons, dimensions, notes, swatch, tier prices and
  preview, supply fields, made-to-order allowance, commission, hide from shop,
  photos, stock by location, cost history and unit-cost correction, kit recipe,
  print label, archive and restore with the impact dialog).

## Managed lists

**Settings → Categories** (`/settings/categories`): the category tree with
sub-categories; add, add sub-category, rename, archive, restore. Each top-level
row shows its sales account (or "Not mapped", posts to the 4000 fallback, with a
link to Category posting), a shop section picker that saves immediately, and its
SKU count. Archive is refused with the server's reason while active SKUs use the
row; archiving a category archives its sub-categories.

**Settings → Materials** (`/settings/materials`): one table per family; add,
rename or change family, archive, restore. Archiving is always allowed and the
notice says how many active SKUs keep the material.

Both are listed under Administration → Catalogue lists and in header-search
destinations; without `catalogue.mutate` they are view-only. Every other picker
(PO line create-SKU, stocktake start, Ledger category posting, CSV import
validation) uses these lists. Nothing creates an entry implicitly.

## Selling rules across Firstout and the shop

A SKU's Sell multiple and Minimum quantity ([ADR 0005](adr/0005-sale-quantity-rule.md)):

| Where | Behaviour |
| --- | --- |
| Firstout till, quotes, new invoice, laybys | Quantity inputs step by the multiple and start at the minimum, with helper text such as "Sold in multiples of 2, minimum 4". The preview flags an off-rule line; saving refuses it with 409 `sale_quantity_rule`, shown on the line. A user with `sales.price_override` may type any quantity and sees "You're breaking a batch". |
| Trade portal | Same stepping from `GET /portal/catalogue`; no authority to break a batch. |
| Shop feed | `include_sell_rules=true` adds `sell_multiple` and `min_quantity`; absent otherwise. |
| DasKasas commerce | Writes both to Medusa variant metadata. Add-to-bag and line updates refuse an off-rule variant total (400, "This piece is sold in sets of 2." / "The minimum order for this piece is 4."); the checkout hold turns an off-rule bag into a review; the purchasable cap is stock rounded down to the multiple. Cart completion, after payment, does not check. |
| DasKasas web | Product page quantity starts at the minimum, steps by the multiple and caps at the rounded-down stock; a price line makes the batch plain; when stock cannot cover the minimum the page says so instead of offering a quantity. The bag stepper uses the same step and never drops below the minimum. JSON-LD carries `eligibleQuantity` when the minimum is above 1. |
| Storefront order intake | Records a paid order whatever its quantities. |

## What deliberately stayed

- `skus.category` (string) stays and always equals the top-level category's
  name; ledger posting, reports, stocktakes and `GET /skus?category=` read it.
  `category_account_maps` stays keyed by name.
- `skus.fabric` stays, not null, as the derived finish label (colour name plus
  main material). The UI never sends it; the API still accepts it, deprecated,
  while a SKU has neither colour name nor main material. Purchase order PDFs and
  packing sheets print it as `Finish:`.
- The deprecated `category` name input stays for API clients and MCP tools; it
  resolves to an existing category or is refused.
- Dropping either column is a later change ([ADR 0006](adr/0006-managed-categories-and-derived-labels.md)).

## Release order

- **Firstout**: migration `120_sku_catalogue_lists` runs before the new backend
  is promoted. It adds three tables and nullable or defaulted columns, backfills
  categories and materials per team, and rewrites `skus.category` to one
  canonical spelling per category. It does not bump `updated_at`, so the shop
  feed does not see a change. Automatic recovery never downgrades the database.
  From reading the schema (not exercised): an older image keeps working against
  the new columns because every new SKU column is nullable or has a server
  default, but it enforces no selling rule and does not set `category_id`, so a
  SKU it creates or recategorises has no shop section until fixed in the new
  release.
- **DasKasas**: safe whichever releases first. An older Firstout ignores
  `include_sell_rules` and omits the keys, which commerce treats as "leave the
  stored value alone" (absent means 1); an older commerce never asks, so
  Firstout never sends them. `verify-live` treats both keys as optional.
- Merging the one PR releases both Apps (P-006).

## Limits

- Activity has no quantities: `unit_cost_audit` rows do not store them, so the
  panel shows source, location, date and note only.
- Photos other than the first cannot be replaced or added from the SKU view;
  that needs backend work outside this build.
- The backfill leaves some colour names and main materials empty by design: a
  text naming two materials, a placeholder fabric, or leftover words that are not
  a recognised colour give null rather than a guess.
- The document-intake create-SKU form (`/proformas/read`) still has a Fabric
  text field and sends `fabric`; it works through the deprecated input but does
  not use the pickers.
- Reorder computes "on order" in its own SQL; the overview and catalogue use
  `on_order_by_sku_id`. The definitions match today.
- The commerce checkout hold still checks stock per line, not per variant; only
  the selling-rule check is per variant.

## Verification

> **Placeholder for the coordinator.** Fill in the real results (commands,
> counts, browser walkthrough and whether it used a local build or a deployed
> service). Nothing here has been verified by this document.
