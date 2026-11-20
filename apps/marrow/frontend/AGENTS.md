> Canonical decisions: [`docs/adr/README.md`](../../../docs/adr/README.md). Follow [P-005](../../../docs/adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../../docs/adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Marrow frontend

- **Token skins:** `app/globals.css` — semantic tokens + `--marrow-*` brand vars (`:root` light / dark)
- **Kit:** primitives and chrome from `@f0rge/ui`; labeled forms from `@f0rge/ui/forms` (see `docs/agents/rules/ui-kit.md`)
- **API client:** `@f0rge/ui/api` — do not re-implement `ApiError` / `handleResponse`
- **Storybook:** `npx nx run f0rge-ui:storybook` — catalogue for shared primitives
- **Never** copy shadcn into `components/ui/` — add primitives in `libs/ui` instead
- Domain widgets (Bristol grid, meal chips, symptom picker) stay in this app

## Branches

Use the `main`-only workflow. A remote `develop` ref may still exist; it is read-only inventory here, not an approved long-lived branch. Do not open pull requests against it, and do not delete the ref or its ruleset from this file. Branch off `main`. Follow P-005 for review/merge; the merge releases Marrow (P-006). See root [`AGENTS.md`](../../../AGENTS.md#git-flow-trunk-based-main-only).
