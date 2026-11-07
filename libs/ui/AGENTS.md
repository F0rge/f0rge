> Canonical decisions: [`docs/adr/README.md`](../../docs/adr/README.md). New apps follow that index. Commands and safety rules below stay in force for the legacy area they name. They are not an approved exception and they do not migrate the app. Leo approves every production release. Do not enable auto-merge, and do not merge or deploy without that approval.

# `@f0rge/ui` — Shared UI Kit

This package is the legacy shared kit for existing apps, not actual Primer and not the new-app design system. Apps consume it only where they already do; never reverse-import. Firstout's Carbon UI is legacy inventory, not an approved exception.

## Adding primitives

1. Add component under `libs/ui/src/components/ui/`.
2. Export from `libs/ui/src/index.ts`.
3. Add a Storybook story when `libs/ui/.storybook` exists.
4. Use **semantic tokens only** (`bg-primary`, `text-muted-foreground`) — never `--marrow-*` or `--dk-*`.

## Engines

`@base-ui/react` and `@mantine/*` stay inside this package. Apps import `@f0rge/ui` and `@f0rge/ui/forms` only.

## Overrides

`libs/ui/src/styles/extras.css` is the only documented override file for kit-level CSS.

## Catalogue

```bash
npx nx run f0rge-ui:storybook
```

Full contract: `.cursor/rules/ui-kit.mdc`. Workflow: `.cursor/skills/add-ui-primitive/SKILL.md`.
