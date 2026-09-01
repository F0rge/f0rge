# Vellano design system (IBM Carbon)

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

Home, Locations, Suppliers, Proformas, Catalogue, **Stock** (menu: Stock, Stocktakes, Adjustments, Import, Reorder), Purchase orders, Transit, Receive, Transfers, Deliveries, Till, Returns, Laybys, Customers, **Books** (menu: Chart of accounts, Contacts, Invoices, Credit notes, Bills, Payments, Bank reconciliation, Reports, VAT201 draft), Users, Profile, Settings.

Stub routes show “Coming in V2-Sx.” — see `apps/vellano/AGENTS.md` V2 shell table.

## S0 screens

1. Home — UIShell + live on-order/on-hand KPIs + quick actions (no S7 hub tables)
2. Login — `vellano_session` cookie auth
