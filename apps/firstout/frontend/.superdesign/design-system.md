# Firstout design system (IBM Carbon)

Product: Gauteng furniture retailer back office (stock, books, till). Not a storefront.

## Visual language

IBM Carbon g10 (light productive). Do not invent a second brand.

- Font: IBM Plex Sans (Carbon default). Productive headings.
- Primary: IBM Blue `#0f62fe`
- Text: `#161616`
- Secondary text: `#525252`
- Background: Carbon gray-10 `#f4f4f4`
- UI shell: header 48px, persistent left side nav
- Spacing: Carbon tokens (`$spacing-05` 16px, `$spacing-06` 24px)
- Radius: Carbon (mostly square / 0)
- No Tailwind, no shadcn, no Marrow tokens

## V2 shell (S0) — SideNav labels

Home, Till, **Sell** (Quotes, Orders, Laybys, Invoices, Returns, Credit notes, Customers), **Products** (Catalogue, Price lists), **Buy** (Reorder, Purchase orders, Proformas, Suppliers), **Warehouse** (Receive, Warehouse on phones only, Transit, Transfers, Picks, Deliveries), **Stock** (Stock on hand, Stock by bin, Stocktakes, Adjustments), **Books** (Bills, Payments, Bank reconciliation, Journals, Repeating invoices, Chart of accounts, VAT201, Books periods), **Reports** (Sales, Stock, Books, Commission), Admin.

Each person sees only the groups and pages their permissions use; the source of truth is `NAV_GROUPS` in `src/lib/nav.ts` (see `apps/firstout/AGENTS.md`, V2 shell). Admin opens the Administration shell: Organisation, Settings, people and roles, Locations, Location defaults, Categories, Materials, MCP tokens, Audit log, Import, Archive, My profile.

Deliveries, Reorder, WMS, and reports extras are live — see `apps/firstout/AGENTS.md`.

## S0 screens

1. Home — UIShell + live on-order/on-hand KPIs + quick actions (no S7 hub tables)
2. Login — `firstout_session` cookie auth
