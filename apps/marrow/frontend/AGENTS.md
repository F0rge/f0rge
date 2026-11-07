> Canonical decisions: [`docs/adr/README.md`](../../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Marrow frontend

- **Token skins:** `app/globals.css` — semantic tokens + `--marrow-*` brand vars (`:root` light / dark)
- **Kit:** primitives and chrome from `@f0rge/ui`; labeled forms from `@f0rge/ui/forms` (see `.cursor/rules/ui-kit.mdc`)
- **API client:** `@f0rge/ui/api` — do not re-implement `ApiError` / `handleResponse`
- **Storybook:** `npx nx run f0rge-ui:storybook` — catalogue for shared primitives
- **Never** copy shadcn into `components/ui/` — add primitives in `libs/ui` instead
- Domain widgets (Bristol grid, meal chips, symptom picker) stay in this app

## Branches

Use the `main`-only workflow. A remote `develop` ref may still exist; it is read-only inventory here, not an approved long-lived branch. Do not open pull requests against it, and do not delete the ref or its ruleset from this file. Branch off `main`. Do not merge or deploy without Leo's release approval. See root [`AGENTS.md`](../../../AGENTS.md#git-flow-trunk-based-main-only).
