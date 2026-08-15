# `@f0rge/ui` — Shared UI Kit

This package is the **only** UI kit for f0rge apps. Apps consume; never reverse-import.

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
