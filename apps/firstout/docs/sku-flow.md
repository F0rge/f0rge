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
| Docked panel | A sibling of `<main>` in the app shell, 28rem wide on the right. When the viewport leaves the page enough room it sits beside the page and `main` gets a right inset; otherwise it lies over the right of the page, which keeps its full width underneath (see Docking). Below 672px it is a full-width sheet. Sections are collapsible groups with a one-line summary; Overview and Stock start open, and open state survives stepping. |
| Full view | The same element grows to cover the content area: same header, same section order. Overview becomes a sticky facts column with the large photo and barcode; the other sections are cards. The page underneath stays mounted and is `inert`. |
| Header search | `/` or Ctrl/Cmd+K. Rich SKU rows (photo, name, Kit tag, ref and category, available, retail), then purchase orders and invoices, and Administration destinations on Administration pages. A live preview of the highlighted SKU sits on the right (hidden at 800px and below). `Enter` on a SKU docks the panel on the current page with every SKU hit as the stepping context; other hits navigate as before. |
| `SkuLink` | A SKU ref rendered as a real link to `/catalogue/{id}` (new tab and middle click work; the link lands in the full view); a plain click docks the panel. Used on receive, transit, picks (list, detail, matrix), stock by bin, supplier price history, purchase order lines, cart lines, reorder, stocktake lines, adjustment lines and inside the panel. |
| Catalogue | `RecordWorkspace` without a details pane (`openRecord`): the table is full width and opening a row docks the panel with the current page of rows as context. Paging, sorting and filtering refresh that context. Filters add Sub-category, Material (main or other), Material family and Do not reorder; Category options come from the managed list. Import, DasKasas import, Export CSV (now with sub-category, colour, materials, order up to, do not reorder and the selling rule), New SKU, label printing and archive/restore are kept. |

Keyboard while the panel is open: `↑` `↓` step through the context (no wrap)
only while focus is inside the panel, so the page keeps its own arrow keys;
`Enter` expands only when the panel itself has focus; `Esc` goes back one level
(full → docked → closed) from anywhere. Keys are left alone while focus is in an
input, select, textarea, combobox, grid, dialog or similar, or a Carbon modal is
open. Opening a row or a search hit moves focus into the panel, so stepping
works straight away. The till's barcode listener claims its own Enter first, so
a scan never also acts on the panel. Closing returns
focus to where it was. Motion is 200 ms on Carbon's productive curve and is off
under `prefers-reduced-motion`.

### Docking

A page sits beside the docked panel only while it keeps its minimum width: 40rem
(640px) by default, 56rem (896px) for a page that calls `useWidePage()`
(`components/sku-panel/provider.tsx`). The cart editor calls it, which covers the
till, quotes and new invoices. Below that the panel overlays the page. The
breakpoints are media queries in `app/globals.css` (nav + 28rem panel + the
page's minimum); Administration pages count their own nav column as an open nav.

| Page kind | Nav open | Nav collapsed |
| --- | --- | --- |
| Default (catalogue, purchase orders, lists) | beside from 1344px | beside from 1136px |
| Wide (till, quotes, new invoice) | beside from 1600px | beside from 1392px |
| Administration (Settings) | beside from 1344px | beside from 1344px |

Below 1056px the nav is compact and the panel always overlays.

## URL parameters

| Parameter | Effect |
| --- | --- |
| `?sku=<id>` | Docks the panel on the current page. |
| `&skuView=full` | Expands it to the full view. |
| `/catalogue/{id}` | Deep link only: replaces itself with `/catalogue?sku=<id>&skuView=full`. Bookmarks, `SkuLink` new tabs, search hrefs and the archive dialog's "Open …" links land there. |
| `/purchase-orders?new=1&prefill_sku=<id>` | Opens the composer with one line for that SKU, its preferred supplier selected when active. |
| `/adjustments?prefill_sku=<id>` | Preselects that SKU for a new or open adjustment. |
| `/picks?prefill_sku=<id>&qty=<n>` | Opens a new pick for that kit (from the till's kit-pick prompt). |
| `/ledger?posting=1` | Opens Category posting (linked from unmapped categories). |

The panel parameters change with `router.replace`, so the page's own route and
state are untouched and `Esc` returns to them exactly. The stepping context (an
ordered list of SKU ids and a label such as `PO-0142` or `Catalogue`) lives in
`SkuPanelProvider`, not the URL. `RecordWorkspace` keeps the parameters when it
writes its own; another page that rebuilds its query string must wrap it in
`withSkuPanelParams`. Prefills use `prefill_sku` (`PREFILL_SKU_PARAM`), never
`sku`, so a prefilled page opens without the panel.

## Sections

All sections read one response, `GET /api/v1/skus/{id}/overview`, plus small
extra reads (Supply: observed lead times; Shop: the category list; Kit: the
recipe).

| Section | Shows |
| --- | --- |
| Overview | Ref, barcode, name, design; Category › Sub-category; colour name with swatch; main and other materials; dimensions, pieces, cartons, notes; Sellable, Do not reorder; status tags. |
| Stock | On hand by location with bins, Held (with its sales orders and laybys), Available, On order, next arrival. Unit cost with `stock.cost.view`. Read-only: stock changes through receiving, transfers and adjustments; the card links to Adjust stock and, for owners (`stock.cost.view` and `users.manage`), offers "Correct cost" per location. |
| Pricing | The four tier prices with the invoice price preview; Sold in multiples of and Minimum quantity, with the "Customers see" line; Earns commission. |
| Supply | Preferred supplier, supplier ref, planned and observed lead time, reorder minimum, order up to, made-to-order allowance; supplier price rows with minimum order and pack multiple. Prices only with `stock.cost.view`. |
| Shop | Readiness (photo, category has a shop section, retail price, dimensions; dimensions is advisory, the feed does not require it), Hide from shop, every photo slot the SKU has. |
| Kit | The recipe for a kit, or the kits this SKU is used in. |
| Activity | The 15 newest cost-audit events: source, location, date, note, and cost with `stock.cost.view`. In the full view, with `stock.cost.view`, also the cost history (`CostAuditPanel`) and last landed cost. |

Archived SKUs show the archived notice and are read-only. Edit controls appear
only with `catalogue.mutate`.

## Editing

Editing happens in the full view, one card at a time. The `CatalogueSkuEditor`
modal, the old price editor and the old `/catalogue/{id}` page are gone.

- **Cards**: Overview, Pricing, Supply (not for kits), Shop and Kit have Edit in
  the card heading. Stock and Activity are read-only. In the docked panel each
  editable group has a small Edit in its summary, which expands to the full
  view with that card already editing and focus on its first field.
- **One at a time**: switching from a clean card swaps directly; from a dirty
  card it asks first. Save and Cancel sit at the card's foot; Enter in a field
  saves; Esc on a clean card ends the edit.
- **Leaving a dirty card** shows an inline "Discard changes to X?" bar with Keep
  editing and Discard. It covers Esc, Collapse, Close, ↑/↓, previous/next, the
  page crumb, a `SkuLink`, header-search results of any kind, the quick
  actions, and any other plain click on a same-origin link (side nav, page
  links, "Manage categories"); Discard then completes the move, and Esc closes
  the bar. Reload and tab close raise the browser's own leave prompt while a
  card is dirty. Browser Back is not guarded (see Limits).
- **Saving** sends only changed fields: Overview and Pricing through
  `PATCH /skus/{id}` (a new multiple always sends the minimum too); Supply
  through `PATCH /skus/{id}`, then `PUT /skus/{id}/supplier-prices` only if the
  rows changed; Shop through the hide-from-shop update, then the photo upload if
  one was chosen; Kit through `PUT /skus/{id}/bom`. On success the overview is
  refetched and the workspace, SKU, category, material, recipe, cost-audit and
  search queries are invalidated. A failed save keeps the draft, puts 422 field
  errors on their inputs (supplier rows per cell) and maps known 409s (ref,
  barcode, duplicate finish, kit) and 403s to a plain message.
- **Overview**: ref, barcode, name, design; Category then Sub-category (each
  category option names the sales account it posts to, or flags the 4000
  fallback); colour name beside the swatch (hex text, colour picker, Clear);
  main material grouped by family and other materials as removable tags;
  cartons, dimensions, pieces, notes; No stock needed (not for kits), Sellable
  and Do not reorder. `Manage categories` and `Manage materials` link to
  Settings.
- **Pricing**: the four tiers with paired VAT, the below-cost warning and the
  invoice price preview; Sold in multiples of and Minimum quantity side by side
  (the minimum follows the multiple until typed; an off-grid minimum shows "Must
  be a multiple of N."); a live "Customers see" line; Earns commission; unit
  cost read-only with `stock.cost.view`.
- **Supply**: preferred supplier, supplier ref, planned lead time (observed lead
  time shown beside it), reorder minimum, order up to, the four made-to-order
  values (all or none), and supplier price rows with minimum order and pack
  multiple. Without `stock.cost.view` there are no price columns and prices are
  sent as null, which keeps the stored ones; only rows added in this edit can be
  removed.
- **Shop**: Hide from shop, readiness, every photo slot, and a first-photo
  upload only while the SKU has no photo.
- **Kit**: the recipe editor (`SkuBomEditor`), saved from the card's foot.
- **Quick actions** in the header, docked and full: Edit price
  (`catalogue.mutate`, not archived; opens Pricing in edit), Print label, Add to
  purchase order (`po.raise`, not archived, not kits;
  `/purchase-orders?new=1&prefill_sku=<id>`), Adjust stock (`stock.receive`, not
  kits; `/adjustments?prefill_sku=<id>`), Archive / Restore (`catalogue.mutate`,
  through the impact dialog). The two navigating actions are real links, so a
  new tab works; a plain click goes through the discard check and lands without
  the panel.
- **Permissions**: no Edit, Archive or Restore without `catalogue.mutate`;
  archived SKUs show the notice and no Edit controls.
- **New SKU** (`/catalogue/new`) uses the same pickers and rules, has no Fabric
  field, and after saving opens the new SKU in the full view. The proforma
  reader's create-SKU form (`/proformas/read`) also dropped Fabric: it sends
  `category_id`, `subcategory_id`, `colour_name` and `main_material_id`.

## Managed lists

**Settings → Categories** (`/settings/categories`): the category tree with
sub-categories; add, add sub-category, rename, archive, restore. Each top-level
row shows its sales account (or "Not mapped", posts to the 4000 fallback, with a
link to Category posting), a shop section picker, and its SKU count. Choosing a
section only stages it: the row states the consequence ("Puts up to N SKUs on
the shop in X.", "Takes up to N SKUs off the shop.", "Moves up to N SKUs on the
shop from X to Y.") and nothing is sent until Save; Cancel restores the saved
value. Archive is refused with the server's reason while active SKUs use the
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
| DasKasas commerce | Writes both to Medusa variant metadata. Add-to-bag and line updates refuse an off-rule variant total with HTTP 400 ("This piece is sold in pairs." for a multiple of 2, "This piece is sold in sets of N." otherwise, "The minimum order for this piece is 4."); the checkout hold turns an off-rule bag into a review, so payment cannot start; the purchasable cap is stock rounded down to the multiple. Cart completion does not check. After payment, the Paystack webhook re-runs the checkout hold, so a rule tightened between payment start and the webhook makes that cart a paid exception for staff, not an order. |
| DasKasas web | The product page works from the variant's total in the bag: it offers the quantities that keep that total on the rule (least to most, in steps of the multiple), capped at stock rounded down to the multiple. A muted price line makes the batch plain ("… each · sold in pairs · … per pair"; "… · minimum 4 · from …"). A piece whose stock or made-to-order capacity cannot cover the minimum reads "Not available to order" on the page, on listing cards and in the availability filter, and is `OutOfStock` in JSON-LD. The bag stepper uses the same step and never drops below the minimum. JSON-LD carries `eligibleQuantity` when the minimum is above 1. |
| Storefront order intake | Records a paid order whatever its quantities. |

## What deliberately stayed

- `skus.category` (string) stays and always equals the top-level category's
  name; ledger posting, reports, stocktakes and `GET /skus?category=` read it.
  `category_account_maps` stays keyed by name.
- `skus.fabric` stays, not null, as the derived finish label (colour name plus
  main material), rebuilt only when the colour or main material really changes
  or a material is renamed. The UI never sends it; the API still accepts it,
  deprecated, while a SKU has neither colour name nor main material. Purchase order PDFs and
  packing sheets print it as `Finish:`.
- The deprecated `category` name input stays for API clients and MCP tools; it
  resolves to an existing category or is refused.
- Dropping either column is a later change ([ADR 0006](adr/0006-managed-categories-and-derived-labels.md)).

## Release order

- **Firstout**: migration `120_sku_catalogue_lists` runs before the new backend
  is promoted. It adds three tables and nullable or defaulted columns, backfills
  categories and materials per team, and rewrites `skus.category` to one
  canonical spelling per category (grouped by Postgres `lower(btrim())`, the
  key the old feed used). It does not bump `updated_at`, so the shop feed does
  not see a change. The rewritten spellings are not restored by the
  migration's downgrade. Take a Firstout database backup before merging.
- **No going back to a pre-merge image**: a failed Release reverts the images
  automatically and leaves the schema at 120, and automatic recovery never
  downgrades the database. A manual `cd.yml` redeploy of Firstout at a pre-merge
  commit is refused by `release_migrate`, so recovery is a fix forward.
  DasKasas and Marrow can be redeployed by hand at the previous commit.
- **Release window**: the old API keeps serving while the migration has run and
  before the new image is promoted. Every new SKU column is nullable or has a
  server default, so its writes succeed, but it enforces no selling rule and
  writes `skus.category` text without touching `category_id`: a SKU it creates
  or recategorises is unlinked or linked to the wrong category, which would put
  it in the wrong shop section or none. The new backend repairs this on every
  start (`relink_sku_categories`, per team, after `ensure_category_chart()`):
  text that matches a top-level category (accents folded) is re-linked to it,
  blank text clears the link, and text that matches no category keeps its
  wording but loses any stale link (category and sub-category cleared), so it
  behaves like any unmapped name: off the shop, posting through the 4000/5000
  fallback. Unmatched names are logged as a warning; nothing is created. Run
  this read-only check after the release (as a role that bypasses RLS, or per
  team after `set_config('app.tenant_id', '<team>', true)`). `startup_action`
  says what the next start does with each row; "unmanaged name, no link" rows
  name a category missing from the managed list (add it in Settings). Plain SQL
  cannot fold accents, so a row whose text differs from its category only by
  accents shows as "unlink: unmanaged name, stale link" although the startup
  leaves it alone: compare `linked_name`.

  ```sql
  SELECT s.team_id, s.id, s.our_ref, s.category AS category_text, c.name AS linked_name,
         m.id AS matching_category_id,
         CASE
           WHEN btrim(coalesce(s.category, '')) = '' THEN 'unlink: blank text'
           WHEN m.id IS NULL AND s.category_id IS NOT NULL THEN 'unlink: unmanaged name, stale link'
           WHEN m.id IS NULL THEN 'unmanaged name, no link'
           ELSE 'relink'
         END AS startup_action
  FROM skus s
  LEFT JOIN sku_categories c ON c.id = s.category_id AND c.team_id = s.team_id
  LEFT JOIN LATERAL (
    SELECT x.id FROM sku_categories x
    WHERE x.team_id = s.team_id AND x.parent_id IS NULL
      AND lower(x.name) = lower(btrim(s.category))
    ORDER BY x.is_archived, x.created_at, x.id LIMIT 1
  ) m ON true
  WHERE (btrim(coalesce(s.category, '')) = '' AND s.category_id IS NOT NULL)
     OR (btrim(coalesce(s.category, '')) <> ''
         AND (m.id IS NULL OR s.category_id IS DISTINCT FROM m.id))
  ORDER BY s.team_id, s.our_ref;
  ```
- Held sales and till baskets saved before this release carry no `kept_qty`,
  so their quantities are checked at the till. Every SKU starts at 1 and 1, so
  this only matters once a rule is set. At the till a saved quote's quantities
  are kept only when the quote can still be sold and its customer is the sale's
  customer, and each quoted line covers one sale line.
- **DasKasas**: safe whichever releases first. An older Firstout ignores
  `include_sell_rules` and omits the keys, which commerce treats as "leave the
  stored value alone" (absent means 1); an older commerce never asks, so
  Firstout never sends them. `verify-live` treats both keys as optional.
- Merging the one PR releases three Apps (P-006): Firstout, DasKasas, and Marrow. Marrow is affected only because the shared `Stepper` in `libs/ui` gained an optional `step`; its behaviour is unchanged. Its whole App (api, worker, mcp, frontend) is released.
- **After the release**, from the delivery review: Firstout `GET /api/v1/ready` answers and Settings → Categories and Materials load; the category check above returns no rows other than known unmanaged names; the shop feed carries `sell_multiple` and `min_quantity` with `include_sell_rules=true`; a pair-sold piece on the storefront shows "sold in pairs"; Marrow's health paths answer; the merge commit has a CI run (a dropped push event releases nothing).

## Limits

- Activity has no quantities: `unit_cost_audit` rows do not store them, so the
  panel shows source, location, date and note only.
- Photos other than the first cannot be replaced or added from the SKU view;
  that needs backend work outside this build.
- The backfill leaves some colour names and main materials empty by design: a
  text naming two materials, a "faux" or "look" material, a colour-capable
  material followed by a colour word, a placeholder fabric, or leftover words
  that are not colour words give null rather than a guess.
- Unsaved card edits are guarded on in-app links (side nav, page links,
  header-search results, the panel's own controls), reload and tab close. Only
  the browser's Back button is not: the panel replaces history entries rather
  than pushing them, so Back leaves the page and the draft is lost.
- A malformed id in a `/catalogue/{id}` link shows the catalogue with no panel
  and no message. A valid deep link (or a reload) takes the catalogue page's
  rows as its stepping context when the SKU is on that page.
- The proforma reader's create-SKU form takes a main material only, no other
  materials.
- Reorder computes "on order" in its own SQL; the overview and catalogue use
  `on_order_by_sku_id`. A test pins the two to the same figures.
- A category can be archived in the same instant a SKU is assigned to it (no
  row lock between the two services); the SKU then sits on an archived
  category, which breaks neither posting nor the feed.
- The commerce checkout hold still checks stock per line, not per variant; only
  the selling-rule check is per variant.

## Verification

Recorded 27 November 2026 at the branch's final commit, on a developer machine.
Nothing here was run against a deployed service.

### Automated checks

| Check | Result |
| --- | --- |
| Firstout backend, full suite (`uv run pytest`, PostgreSQL 16 in testcontainers) | 1,279 passed |
| Firstout backend `ruff check` and `ruff format --check` | clean |
| `nx run-many -t typecheck,lint,test,build` for `firstout-frontend`, `daskasas-web`, `daskasas-commerce`, `f0rge-ui`, `marrow-frontend` | all pass (lint: 0 errors) |
| `firstout-frontend:codegen:check` | passes |
| DasKasas browser specs on the synthetic fixture (`sell-rules`, `product`, `bag-checkout`) | 21 passed |
| `npm run agents:check` | passes |

### Walkthrough

The Firstout walkthrough used a local harness kept outside Git: the working
tree's real frontend under `next dev`, the real FastAPI app as a restricted
database role with tenant isolation enforced, the schema built by the real
migrations to `120_sku_catalogue_lists`, and the app's playground seed. Only
the Clerk modules and the identity provider were replaced. It does not prove
real Clerk sign-in, tenant-host routing, the production build's runtime, or
production database grants.

Walked as **owner**:

- Catalogue with a category filter and a checked row: open a row, step with
  the arrow keys, expand, edit Pricing (the minimum follows the multiple; a
  minimum of 3 with a multiple of 2 is refused; the "Customers see" line
  updates), the discard bar on `Esc`, save, then back out to the list with the
  filter and the checked row intact. No console errors or failed requests.
- Header search from Purchase orders and from Settings: rich results, live
  preview, `Enter` docks the panel on the page; a purchase order hit is listed
  in its own group.
- The catalogue docks beside the panel at 1440px; the panel at 390px is a
  full-width sheet with editing and the discard bar working, and no horizontal
  page scroll.
- Settings → Categories and Materials; a shop-section change is staged with
  "Takes up to 12 SKUs off the shop." and nothing is sent until Save.
- Reorder lists a seeded SKU with Order up to, Minimum order and Pack multiple.
- "Add to purchase order" lands on the composer with `prefill_sku` and no panel.
- The new SKU page has no Fabric field; `/catalogue?sku=<unknown>` shows
  "SKU not found" and `Esc` closes it; reduced motion removes the transitions.

Walked as the **till** user (no `catalogue.mutate`, `sales.price_override` or
`stock.cost.view`): the full view shows no edit controls, costs or archive
action; both Settings screens are view-only; on the till a SKU sold in
multiples of 2 with a minimum of 4 starts at 4 and steps by 2, and a quantity
of 3 is blocked with the rule's message, while the owner gets the "You're
breaking a batch" notice instead.

Against the harness API, as both identities (32 checks, all passing): the till
user is refused SKU, category and supplier-price writes (403) and receives no
costs; a quote at an off-rule quantity is refused with `sale_quantity_rule`; a
quote saved before the rule was tightened previews clean at the till for its
own customer, and is still checked for another customer or at a changed
quantity; reorder rounds to the pack multiple and drops a do-not-reorder SKU;
a sub-category cannot have children; a category in use cannot be archived; a
rename reaches the SKU's category text; an unknown category name and an
unknown shop section are refused; "Boucle" is refused beside "Bouclé"; the
finish label is derived from colour and material; search treats `%` literally.

The shop was checked on the storefront's synthetic fixture at 375px: a piece
sold in pairs, one sold in pairs with a minimum of 4, and one whose stock
cannot cover its minimum ("Not available to order", Add to bag disabled).

### Not walked in a browser by the coordinator

The layby, new-invoice and trade-portal quantity inputs (the harness has no
customer login), photo upload, the CSV import screen, the ledger's category
posting picker and an archived SKU. These rest on the backend suite and on the
implementing agents' own walkthroughs.

### Independent review

Security, data, backend, frontend (shop and Firstout), quality and delivery
reviews were run by separate agent instances. None found a blocker; their
should-fix findings were fixed on the branch. Accepted, not fixed: the browser
Back button with unsaved card edits; a paid shop cart becoming a staff
exception if a rule is tightened between payment and the payment webhook; the
reorder list computing "on order" in its own query (pinned to the shared
definition by a test).
