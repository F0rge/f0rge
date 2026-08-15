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
