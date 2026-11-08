# Frontend

These records use the temporary register IDs. They become the repo's canonical decisions only after this change is reviewed, approved, and merged. The planning Page stays a planning aid, not a second policy copy.

Policy status `Accepted` means the decision was agreed. It does not mean the software already implements it. `Conditional` means the selection is not accepted policy. Proposed enforcement is not installed. No legacy app is an approved exception.

## P-023

- **Policy status:** Accepted
- **Temporary ID:** P-023
- **Category:** Frontend
- **Decision:** Standalone React frontend; Rust owns the backend.
- **Proposed enforcement (not installed):** Frontend template and package/build inspection enforce the SPA entrypoint; dependency policy flags unapproved server frameworks or duplicated backend endpoints.
- **Gate and limit:** Static + build smoke: frontend artifact and API integration test. No additional Node backend is required by chosen TanStack libraries.
- **Static evidence at `f155a2ba` (not normative, not a live check):** No package policy flags Next.js or a second backend.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-024

- **Policy status:** Accepted
- **Temporary ID:** P-024
- **Category:** Frontend
- **Decision:** Strict TypeScript for React apps and shared frontend packages.
- **Proposed enforcement (not installed):** Shared tsconfig with strict enabled; effective-config audit prevents per-app weakening; tsc no-emit and reviewed escape-hatch suppression report.
- **Gate and limit:** Static: typecheck and effective tsconfig evidence. Strict typing is not runtime validation or authorization.
- **Static evidence at `f155a2ba` (not normative, not a live check):** tsc --noEmit scripts exist for several Next apps and run via nx affected when those targets exist. No effective-config audit blocks a stricter flag being turned off.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-025

- **Policy status:** Accepted
- **Temporary ID:** P-025
- **Category:** Frontend
- **Decision:** Vite is the default frontend development/build tool.
- **Proposed enforcement (not installed):** Template and package-script/config policy; production build and static-serving smoke tests run with pinned dependencies.
- **Gate and limit:** Static + test: build artifacts and direct-link smoke evidence; no new framework selected implicitly.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None that require Vite for a new app.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## P-026

- **Policy status:** Accepted
- **Temporary ID:** P-026
- **Category:** Frontend
- **Decision:** Use actual Primer as the single shared design system, not merely a similar appearance.
- **Proposed enforcement (not installed):** Shared UI package depends on Primer; restricted imports direct apps through approved shared bricks; dependency graph flags competing design systems.
- **Gate and limit:** Static + browser + human: Primer provenance and component review. Import checks cannot prove every screen uses the intended design language.
- **Static evidence at `f155a2ba` (not normative, not a live check):** ESLint no-restricted-imports blocks @base-ui and @mantine in app frontends that spread the shared config. It does not require Primer. It does not cover Firstout's Carbon imports as a violation of Primer.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-027

- **Policy status:** Accepted
- **Temporary ID:** P-027
- **Category:** Frontend
- **Decision:** Default Primer tokens unless Leo specifies a custom theme; custom themes retain accessibility.
- **Proposed enforcement (not installed):** Typed shared theme boundary and token rules; approved theme record linked from brief; contrast and interaction tests run for each supported theme.
- **Gate and limit:** Static + test + human: theme approval and accessibility evidence. No automatic permission for arbitrary redesigns.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for theme approval or contrast.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-028

- **Policy status:** Accepted
- **Temporary ID:** P-028
- **Category:** Frontend
- **Decision:** Share reusable UI bricks repo-wide, not app-specific screens/business rules.
- **Proposed enforcement (not installed):** UI package dependency boundaries prohibit app-domain imports; package exports define supported components; app screens compose those bricks locally.
- **Gate and limit:** Static + review: import graph and shared-API review. Do not force every app-specific composite into the shared library.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Nx module boundaries for five scope tags, plus restricted engine imports. scope:buycycle and scope:envmon are not in the depConstraints list. The boundary check is static imports only.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## P-029

- **Policy status:** Accepted
- **Temporary ID:** P-029
- **Category:** Frontend
- **Decision:** Storybook is the place to inspect and test shared UI bricks.
- **Proposed enforcement (not installed):** Shared-component story coverage check, buildable Storybook and interaction/accessibility scenarios; attach inspectable output to development evidence.
- **Gate and limit:** Build + test + human: Storybook artifact and browser results. Hosting/access location still needs assessment; no public publishing implied.
- **Static evidence at `f155a2ba` (not normative, not a live check):** storybook-build is in the frontend nx affected target list. No check that every export has a story. No committed Storybook hosting URL.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## P-030

- **Policy status:** Accepted
- **Temporary ID:** P-030
- **Category:** Frontend
- **Decision:** TanStack Query around generated API clients is the standard server-data approach.
- **Proposed enforcement (not installed):** Shared query/mutation conventions; test loading/error/invalidation and org/user cache separation; review retry policy and conflict behavior.
- **Gate and limit:** Static + test: dependency/client integration and cache-isolation tests. Cache is not authorization; do not blindly retry consequential mutations.
- **Static evidence at `f155a2ba` (not normative, not a live check):** No lint rule requires TanStack Query. No test name search was treated as proof of cache isolation.
- **Implementation:** Partial static evidence only. This record does not claim the decision is built.
- **Assessment label:** partial (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## P-031

- **Policy status:** Accepted
- **Temporary ID:** P-031
- **Category:** Frontend
- **Decision:** TanStack Router is the default router.
- **Proposed enforcement (not installed):** Typed route/search conventions and route generation check; browser tests cover deep links, invalid search inputs and denied routes.
- **Gate and limit:** Typecheck + browser: route tests against built SPA. UI route guards do not replace backend permissions.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## P-032

- **Policy status:** Accepted
- **Temporary ID:** P-032
- **Category:** Frontend
- **Decision:** TanStack Form with shared, tested Primer adapters.
- **Proposed enforcement (not installed):** Shared form adapter package; test labels, keyboard behavior, server field errors, submission, pending state and conflict handling.
- **Gate and limit:** Typecheck + browser: adapter and app form tests. Generated Zod integration remains conditional, not already proven.
- **Static evidence at `f155a2ba` (not normative, not a live check):** ESLint blocks apps from importing @mantine/form directly. It does not require TanStack Form or Primer adapters.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## P-034

- **Policy status:** Accepted
- **Temporary ID:** P-034
- **Category:** Frontend
- **Decision:** WCAG 2.2 AA target, with automated checks plus keyboard and screen-reader checks on core journeys.
- **Proposed enforcement (not installed):** Storybook/Playwright accessibility scans, keyboard focus journeys and recorded manual assistive-technology review; custom themes included.
- **Gate and limit:** Test + human: scan results and journey-specific manual evidence. Automated scanners do not certify complete WCAG conformance.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Playwright smoke for Marrow when selected. It is not an accessibility gate. No keyboard-journey artifact is required.
- **Implementation:** Pending. This record does not claim the decision is built.
- **Assessment label:** gap (read-only assessment, not a gate).
- **Risk noted in that assessment:** medium.
- **Approved exception:** None.

## C-001

- **Policy status:** Conditional
- **Temporary ID:** C-001
- **Category:** Frontend
- **Decision:** Generated Zod runtime validation is the proposed frontend direction, only after proving Rust-contract → TanStack Form integration.
- **Proposed enforcement (not installed):** Timeboxed proof using representative field constraints, nested/optional/null fields and server errors; shared valid/invalid fixtures, deterministic generation and adapter tests.
- **Gate and limit:** Proof + human: successful integration evidence before making generator/tool/version mandatory. Not an installed or proven pipeline.
- **Static evidence at `f155a2ba` (not normative, not a live check):** None for a Rust-to-Zod generator.
- **Implementation:** Conditional, not accepted. This record does not claim the decision is built.
- **Assessment label:** conditional (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

## C-002

- **Policy status:** Conditional
- **Temporary ID:** C-002
- **Category:** Frontend
- **Decision:** Proposed test standard: Vitest for logic; Storybook real-browser shared UI tests; Playwright critical whole-app journeys against production builds. React Testing Library selectively, subject to repo compatibility.
- **Proposed enforcement (not installed):** Pilot verifies chosen versions/build modes, CI browser support, accessibility integration and representative scenarios; retain useful existing tests while evaluating compatibility.
- **Gate and limit:** Pilot + CI: deterministic unit/browser/end-to-end results and traces. Tooling compatibility and exact runner setup are not assumed verified.
- **Static evidence at `f155a2ba` (not normative, not a live check):** Those tools run where wired. They are not adopted as the platform standard, and this assessment did not execute them.
- **Implementation:** Conditional, not accepted. This record does not claim the decision is built.
- **Assessment label:** conditional (read-only assessment, not a gate).
- **Risk noted in that assessment:** low.
- **Approved exception:** None.

