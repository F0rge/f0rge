---
name: add-ui-primitive
description: Add a new shared UI primitive to libs/ui — component file, index export, Storybook story, semantic tokens only. Use when adding a shadcn/Base UI primitive, extending the design system, or when an agent would otherwise copy components into apps.
paths:
  - libs/ui/**
  - apps/**/frontend/**
---

# Add UI Primitive

Add a reusable primitive to `@f0rge/ui`. Apps never get local copies.

Read `.cursor/rules/ui-kit.mdc` and `libs/ui/AGENTS.md` before starting.

## Steps

1. **Create component** at `libs/ui/src/components/ui/<name>.tsx`.
   - Semantic tokens only (`bg-primary`, `text-muted-foreground`).
   - Base UI `render` prop — not Radix `asChild`.
   - Engines (`@base-ui/react`, `@mantine/*`) stay in this file only.

2. **Export** from `libs/ui/src/index.ts`.

3. **Storybook story** — when `libs/ui/.storybook` exists, add `libs/ui/src/components/ui/<name>.stories.tsx`. Skip until Storybook is set up; note in PR.

4. **CSS overrides** — only via `libs/ui/src/styles/extras.css` if needed.

5. **Verify** — no new files under `apps/**/components/ui/`; app imports use `@f0rge/ui`.

```bash
npx nx run f0rge-ui:lint
npx nx run f0rge-ui:typecheck
# When Storybook exists:
npx nx run f0rge-ui:storybook
```

## Do not

- Copy shadcn output into `apps/marrow/frontend/components/ui` or `apps/dk/tag-printer/frontend/components/ui`
- Use `--marrow-*` or `--dk-*` in lib components
- Export Mantine or Base UI types to apps — wrap them

## Acceptance

- [ ] Component in `libs/ui/src/components/ui/`
- [ ] Exported from `src/index.ts`
- [ ] Storybook story (when `.storybook` exists)
- [ ] No app-side primitive copy
- [ ] Semantic tokens only
