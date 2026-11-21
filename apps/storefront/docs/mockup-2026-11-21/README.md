# DasKasas shop mockup (21 Nov 2026)

The approved look for the storefront rebuild. This is a reference, not a runnable app in the workspace: it was built as a throwaway Vite + React 19 + Tailwind v4 + shadcn/ui prototype from the free blocks at shadcn-ui-blocks.com, and published as a Claude artifact for review.

- `NOTES.md`: pages, blocks used per page, routes and where the content lives.
- `src/pages/*`: one file per page; `src/components/blocks/**`: the installed free blocks, already adapted (e.g. the feature-tabs fix for shadcn Tabs v4).
- `src/content.ts`: the showroom facts and the six real catalogue pieces used as sample data. The live shop must read the catalogue from Medusa, not from this file.
- The Arc sofa photos it used live in `apps/storefront/web/public/demo/`.

To run it standalone: copy the folder somewhere outside the repo, `npm install`, `npm run dev`.
