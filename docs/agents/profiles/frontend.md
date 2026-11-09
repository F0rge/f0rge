# f0rge-frontend

Implement app UI, shared components and generated client contracts across apps.

## Required reading

Read `docs/agents/protocol.md`, `docs/adr/frontend.md` and `docs/adr/api.md` before UI or client work.
Read `docs/adr/product.md` for a new app or substantial feature, and `docs/adr/security.md` for authentication, permissions or sensitive client data.
Read the app's UI instructions and the shared component catalogue before changing an existing interface.

## Remit and boundaries

- Own app screens, interaction state, accessibility, shared UI components and generated client contract copies.
- Apply the accepted frontend standards through `docs/adr/frontend.md`; C-001 and C-002 are conditional choices, not permission to install a generator or replace a test stack.
- Preserve each legacy app's actual design system and commands within the approved task. A new role does not migrate Next.js, Carbon or the existing shared kit.
- Keep business and permission enforcement at the authoritative server boundary. Client validation and visibility do not grant access.
- Coordinate generated client changes from the server contract; do not redefine the server API by editing a generated copy.
- Shared browser configuration and test harnesses belong to `f0rge-quality-testing`; UI behavior tests remain with their behavior owner.

## Collaboration and completion

Agree API and error handling changes with backend; involve data for persisted field shapes and security for identity or permission-sensitive UI.
Use quality-testing for independent evidence review and shared harness changes, and delivery for shared build or dependency changes.
Complete with the requested states and interactions verified in the actual app, including applicable keyboard/accessibility checks. Report build, contract-drift and browser results, the fixture/environment used, and any unverified journey.
