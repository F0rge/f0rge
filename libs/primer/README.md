# Shared Primer bricks

`@f0rge/primer` exposes actual `@primer/react` components and its default automatic
light/dark theme. It introduces no app-specific screen or brand skin. Apps compose
screens locally and import these shared bricks rather than competing UI engines.

The shared entry point loads the required pinned Primer primitives and functional
light/dark theme CSS. `PrimerProvider` follows the system colour scheme and gives
its full-height `BaseStyles` surface the default Primer canvas and foreground,
including loading and denied screens. It also works in the Storybook decorator
without application HTML attributes. Apps initialise `data-color-mode="auto"`,
`data-light-theme="light"` and `data-dark-theme="dark"` on their root HTML element
so the document canvas and portals use the same defaults before React starts.
No application palette or duplicated token values are required.

See [Primer's React setup](https://primer.style/product/getting-started/react/).

`@f0rge/primer/forms` supplies the shared TanStack Form `usePrimerForm` hook,
labelled text/number/date/URL field and pending submit button. It connects field
value/blur/change, public client/server validation messages and submit state to
Primer controls. `@f0rge/primer/api` maps the shared safe API envelope, including
field errors, permission denial and edit conflicts; it never displays arbitrary
raw failed-service detail.

```sh
npx nx run f0rge-primer:typecheck
npx nx run f0rge-primer:lint
npx nx run f0rge-primer:test
npx nx run f0rge-primer:storybook-build
npx nx run f0rge-primer:storybook
```

The catalogue covers actions, loading/denied/conflict/success states, validation
and a real shared TanStack form. Storybook is development-only and not publicly
published by these commands. Three pure public-error/validation regressions pass;
the built catalogue's form was also tested in Chromium for labels, submit and
keyboard focus. Buycycle's production-build browser tests exercise the actual
shared adapter through saving and conflict states.

This uses test tools for this implementation; it does not turn conditional ADRs
C-001 or C-002 into a repository-wide selection. No generated Zod adoption is
introduced. No production app is migrated merely by adding this library.
