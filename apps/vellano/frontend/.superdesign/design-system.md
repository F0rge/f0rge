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

## S0 screens

1. Home — UIShell + side nav placeholders + API health status
2. Login — placeholder form (email/password disabled). Cookie later: `vellano_session`

Side nav labels (placeholders only): Home, Stock, Purchase orders, Ledger, Till, Settings.
