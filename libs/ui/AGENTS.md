> Canonical decisions: [`docs/adr/README.md`](../../docs/adr/README.md). Follow [P-005](../../docs/adr/governance.md#p-005) for review/automatic squash merging. A reviewed merge to `main` releases the affected Apps ([P-006](../../docs/adr/governance.md#p-006)). Legacy commands below remain inventory, not approved exceptions.

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

Full contract: `docs/agents/rules/ui-kit.md`. Add shared primitives here with public exports and Storybook coverage.
