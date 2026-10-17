# Buycycle dashboards — design & UX critique (Primer v2, 17 Oct 2026)

Reviewed: /workspace/undervalued-{bikes,wheels}/primer-*.png and bc-tracker/v2/index.tpl.html (served from the Pi :8095/:8096).

## Information hierarchy
- Good: one job per page (find resale deals), KPI strip, default sort by € profit, tabs for secondary views.
- Weak: every row looks the same, so a €4,471 high-confidence deal and a marginal one have equal visual weight. Nothing says "act on this".
- "Watchlist 0" holds a KPI slot without helping you decide anything.
- "Model STR / DTS" shows "0% / –" on every row (only one snapshot so far). It's a dead column that takes width and attention.

## Scanability of deals
- The Listing cell mixes title, brand, size, year, condition and groupset in small muted text. It wraps to 3 lines, so only about 9 rows fit on screen.
- Comps badge, "comparables" disclosure and ref price are stacked in one cell. That's dense, but OK.
- Risk badges are clear (red/amber), but "thin description" is so common that it turns into noise.

## Sorting / filtering
- Strong: URL-persisted filters, sortable headers with aria-sort, mobile bottom sheet, risk/confidence/flex filters.
- Weak: the 16-field filter column is long and unordered, and the most-used filters (min profit, confidence, max km) sit below the fold. Sort lives twice (header click + "Sort by" select), so it's easy to get confused about which one wins.

## How clear the undervaluation is
- "Disc. 43.6%" is a bare percentage, so you have to work out the € gap yourself from Price vs Ref.
- The reference quality (comp count/spread) is the key trust signal, but nothing tied it visually to the discount.

## Mobile
- Cards are good: big price, 6-stat grid, 44px targets, bottom nav, infinite scroll.
- The manual "Desktop"/"Switch to mobile" toggle (plus the 'v' key and the #view= / localStorage override) can trap a phone in the desktop layout. A responsive page shouldn't need it.
- The KPI strip scrolled sideways and clipped ("Median ROI (…"), so half the KPIs were never seen.

## Accessibility
- OK: real buttons, aria-sort, aria-pressed on watch, labelled inputs, focus-visible on headers.
- Gaps: the watch button label was just "Watch" (every row has the same name), there was no skip link, the table had no caption, profit/loss was shown by colour only in places, and the general focus ring was inconsistent.

## Performance
- Good: top.json (85 KB) gives a fast first paint before data.json (4.5 MB, gzip-served), details/models load lazily, and vendor assets are cached for a week.
- Remaining: the full data.json still parses about 16k rows on phones. Desktop renders 200 rows per page via innerHTML, which is fine. Possible next step: drop gone listings from data.json, or paginate by kind.

## Implemented (PR branch feat/responsive-ux)
1. Purely responsive: the layout comes only from the viewport (CSS media queries for show/hide, plus a matchMedia listener for JS rendering). The toggle buttons, the 'v' key, the #view= hash and the localStorage override are removed. I checked that resizing desktop→390px switches automatically.
2. "Strong deal" highlight: profit ≥ €250, ROI ≥ 15%, ≥20% under ref, medium+ comp confidence, no hard risk flag. Marked by a green left rule and label (desktop and cards), and it replaces the Watchlist KPI.
3. Undervaluation made explicit: the "Under ref." column shows the %, the € gap and a small bar; mobile cards show the € gap too.
4. The STR/DTS column is hidden until sell-through history exists.
5. Mobile KPIs are now a 3×2 grid (no clipped scroller).
6. A11y: skip link, table caption that defines "strong deal", watch buttons named per listing, global focus-visible ring.
Not done (suggested next): reorder/group filters, collapse the duplicate sort control, slimmer data.json.

## Round 2: strict Primer audit (Leonardo's feedback: the mobile cards weren't Primer)
| Was (custom) | Now (Primer) |
|---|---|
| Custom `.card` deal cards, `.stats` tiles | `Box` + `Box-row` list, Primer typography/colour utilities (`f2`, `text-semibold`, `color-fg-success`) |
| Hand-rolled `table.DataTable` CSS (sticky header, hover, selection) | Primer React DataTable CSS (`prc-DataTable-*`, vendored verbatim from @primer/react 38.42.0) with `data-cell-padding`/`data-cell-align`, sort via `Button--invisible` and `aria-sort`, selection via `color-bg-accent` |
| Custom bottom sheet + backdrop for filters | Native `<dialog>` with Primer `Overlay` (`Overlay--placement-bottom-whenNarrow`, header/body/footer, `Overlay-closeButton`) |
| Custom fixed bottom tab bar with hand-drawn SVGs | `UnderlineNav` with Octicons (one nav for every width, scrolls horizontally on phones) |
| Custom shortcuts popup | `Overlay` dialog + `ActionList` |
| Custom progress bar | `Progress Progress--small` |
| Custom "strong" accent border | `Label Label--success` |
| Text "8 comps · medium" badge | `Counter` (count) + `Label` (confidence) |
| Legacy `.btn`/`btn-octicon` and ☆ glyph | `Button` (primary/secondary/invisible/danger, iconOnly) + Octicons `star`/`star-fill` |
| `.form-control`/`.form-select`, risk/confidence dropdowns | `FormControl` inputs/selects; `SegmentedControl` for confidence and risk |
| KPI flex scroller, `.num/.pos/.neg/.hide/.tap/.skip` | Primer grid (`col-4 col-lg-2`, `gutter-condensed`), `text-right` via data-cell-align, `color-fg-*`, `[hidden]`, `show-on-focus` |
| JS `data-layout` + `only-d/only-m` CSS | Primer responsive utilities `d-none d-md-block` / `d-md-none` (pure CSS) |
Filters regrouped (Find / Price & return / Trust & risk / Location & age). The duplicate sort is gone: one sort state, set by the DataTable headers on desktop and one select on mobile.
