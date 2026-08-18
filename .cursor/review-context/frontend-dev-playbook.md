# Frontend Review Playbook

> **Agent auto-context:** `.cursor/rules/ui-kit.mdc` (globs cover `libs/ui` + all app frontends).
> **Bugbot:** `.cursor/BUGBOT.md` (Nx gates + UI kit import bans).
> **This playbook is manual** — nothing loads it automatically; read when reviewing PRs.

## What this is

Repo-specific checklist for reviewing frontend diffs in this repo. Contains hard rules derived from real incidents and post-mortems in this codebase — not generic React advice.

---

## Scope — what files this playbook covers

- `apps/marrow/frontend/app/**` (App Router pages, layouts, route segments)
- `apps/marrow/frontend/components/**`
- `apps/marrow/frontend/lib/**` (api client, hooks, utils)
- `apps/marrow/frontend/hooks/**`
- `apps/marrow/frontend/public/**`
- `apps/marrow/frontend/package.json`, `apps/marrow/frontend/tsconfig.json`, `apps/marrow/frontend/next.config.*`
- `apps/dk/tag-printer/frontend/**` — dk tag printer Next.js app
- `libs/ui/**` — shared `@f0rge/ui` component library

NOT in scope for this playbook: `.github/`, `apps/marrow/backend/`, `apps/dk/tag-printer/backend/`, `libs/backend/`, `docker-compose*.yml`, migration files.

**Non-duplication:** block re-implementations of `@f0rge/ui` primitives, API client, or shared hooks. See `ui-kit.mdc` for import and token rules.

---

## Hard rules — instant block findings

**UI kit (mirrors `.cursor/BUGBOT.md` + `ui-kit.mdc`):**

- **`apps/**` imports `@base-ui/react` or `@mantine/*`** — engines stay in `libs/ui`.
- **New shadcn primitive under `apps/**/components/ui`** — add to `libs/ui` + Storybook instead.
- **`CompactStepper` or other stepper fork** instead of `@f0rge/ui` `Stepper`.
- **New `libs/ui` primitive without Storybook story** — when `libs/ui/.storybook` exists.
- **Brand tokens (`--marrow-*`, `--dk-*`) in `libs/ui` TSX** — brand vars belong in `libs/ui/src/styles/skins/` only.

**1. dnd-kit on 2D grid must use `rectSortingStrategy`, NOT `verticalListSortingStrategy`.**
`verticalListSortingStrategy` only works on single-column lists. The check-in card grid is CSS `grid-cols-12` at desktop. Using the wrong strategy causes cards at the same vertical position to swap incorrectly.
*Cites: `frontend-dev/dnd_kit_grid_drag_reorder.md`*

**2. dnd-kit listeners must live on the drag handle only.**
`{...listeners} {...attributes}` belong on a dedicated `<button>` with a `GripVertical` icon. Spreading them on the card wrapper blocks clicks on form inputs, buttons, and sliders inside the card. `ref={setNodeRef}` and `style={transform/transition}` go on the outer wrapper.
*Cites: `frontend-dev/dnd_kit_grid_drag_reorder.md`*

**3. col-span classes must be on the sortable wrapper node, not the inner card.**
dnd-kit sets `transform` on the `ref` node. If col-span lives on an inner `<Card>`, the outer ref div is 0-height and the transform displaces wrong. col-span moves to the node with `ref={setNodeRef}`, and `h-full` is added to the inner card.
*Cites: `frontend-dev/dnd_kit_grid_drag_reorder.md`*

**4. DragOverlay sizing: capture `rect.width` at `onDragStart`, apply as `style={{ width }}`.**
Without an explicit width, DragOverlay renders outside the CSS grid with no parent to constrain it — collapses or stretches on mobile. Pattern:
```tsx
const handleDragStart = useCallback((event: DragStartEvent) => {
  setActiveId(event.active.id as CardId)
  const rect = event.active.rect.current.initial
  setDragOverlayWidth(rect ? rect.width : undefined)
}, [])
// In JSX:
<DragOverlay>
  {activeId !== null ? (
    <div style={{ width: dragOverlayWidth }}>
      {cardRenderers[activeId]()}
    </div>
  ) : null}
</DragOverlay>
```
*Cites: `frontend-dev/dnd_kit_grid_drag_reorder.md`*

**5. DndContext only mounted when reorder mode is active.**
`isReorderMode=false` (normal view): cards render at full content, no drag overhead. `isReorderMode=true`: tiles replace card content, DndContext wraps only the tile list. Block any PR that keeps DndContext mounted unconditionally on the check-in page.
*Cites: `frontend-dev/reorder_mode_pattern.md`*

**6. No `eslint-disable` for `react-hooks/set-state-in-effect`.**
Use the key-bump pattern instead: parent tracks `errorKey: number`, passes `key={errorKey}` to the component and `shakeOnMount={errorKey > 0}`. The component initializes state from the prop (`useState(shakeOnMount)`). The rule is pointing at a real design smell; silencing it hides the issue and blocks CI re-enablement.
*Cites: `frontend-dev/react-hooks-set-state-in-effect.md`*

**7. `'use client'` does NOT skip SSR — localStorage in `useState(initializer)` = hydration mismatch.**
App Router prerenders `'use client'` pages at build time (`○` in `npm run build` output). `useState(loadCardOrder)` fires on the server (returns default), then again on the client (returns saved value) — React throws a hydration error. Three acceptable fixes in preference order:
- `useSyncExternalStore` with `getServerSnapshot` returning the stable default (lint-clean, preferred)
- `useState(DEFAULT)` + `useEffect(() => { setState(saved) }, [])` (triggers `react-hooks/set-state-in-effect` on small components where React Compiler succeeds)
- `next/dynamic({ ssr: false })` (last resort)

The `useSyncExternalStore` pattern:
```tsx
const cardOrder = useSyncExternalStore(
  subscribeCardOrder,            // module-level subscriber set
  () => loadCardOrder(),         // getSnapshot (client only)
  () => [...DEFAULT_CARD_ORDER], // getServerSnapshot (SSR + hydration)
)
```
*Cites: `frontend-dev/customize_hub_foundation.md`*

**8. No duplicate `ICON_MAP` — import `ICON_COMPONENT_MAP` from `IconPicker.tsx`.**
`KNOWN_ICONS` (readonly string[]) and `ICON_COMPONENT_MAP` (name → LucideIcon) are exported from `components/checkin/cards/components/IconPicker.tsx`. TrackerRow and any future tracker-style component must import from this single source. DB key for `BookOpen` is `bookopen` (no space). Block any new local icon map definition.
*Cites: `frontend-dev/icon_picker_pattern.md`*

**9. Tracker card dual-source contract must be respected.**
Seeded tracker values (Alcohol units, Caffeine servings, Sick, Hot shower — identified by `is_seed` flag or `SEEDED_NAMES` Set) flow through CheckinBoard props and the existing autosave path. Custom tracker values go through `useEntryTrackerValues(date)` + `useUpsertTrackerValue(date)` with optimistic updates. Routing seeded writes through the custom endpoint = double-write race. Routing custom writes through props = misses backend `tracker_log`.
*Cites: `frontend-dev/trackers_dual_source_card.md`*

**10. Tracker archive/restore invalidation must use prefix key `['trackers']`.**
`queryClient.invalidateQueries({ queryKey: ['trackers'] })` invalidates both `['trackers', false]` and `['trackers', true]` simultaneously. Explicitly invalidating only one variant leaves the other stale. Manage footer must be hidden when `archivedTrackers.length === 0`.
*Cites: `frontend-dev/trackers_manage_restore.md`*

**11. `asChild` prop does not exist in base-ui shadcn — use `render` prop.**
```tsx
// WRONG:
<DialogTrigger asChild><Button>Open</Button></DialogTrigger>
// CORRECT:
<DialogTrigger render={<Button />}>Open</DialogTrigger>
```
`Select.onValueChange` callback receives `value: T | null` — always null-guard before using the value.

**12. 204 No Content must be handled before content-type sniff.**
FastAPI sets `Content-Type: application/json` on 204 responses with no body. `res.json()` on a 204 throws `SyntaxError: Unexpected end of JSON input`, propagates through mutations, shows a red toast even though the backend succeeded. In `handleResponse` or any custom fetch wrapper:
```ts
if (res.status === 204) return null  // MUST be before content-type check
```
This affects every DELETE endpoint. Issues #11 and #12 were the same bug filed independently.

**13. `field || undefined` in PUT/PATCH body silently prevents clearing.**
`notes: notes || undefined` in a PUT body → empty string becomes `undefined` → `JSON.stringify` drops the key → backend `model_dump(exclude_unset=True)` leaves the DB column unchanged → user clears the textarea, saves, value reverts on refetch. Always send the value for user-editable fields: `notes: notes`. Exception: conditionally-applicable fields like `bristol_type` (only valid when `stool_status === 'abnormal'`) legitimately use `undefined`.

**14. Parameter-less `catch {}` must not be used.**
`catch { toast.error('Failed') }` collapses 409 (conflict), 422 (validation), and 500 under one toast. Branch on error type:
```ts
} catch (err) {
  if (err instanceof ApiError && err.status === 409) { /* handle conflict, invalidate query */ }
  else if (err instanceof ApiError && err.status === 422) { /* parse detail string or [{msg,loc}] array */ }
  else { console.error(err); toast.error('Failed. Please try again.') }
}
```
`ApiError` is exported from `lib/api/client.ts`.

**15. TypeScript strict — no `any` in new code.**
`tsconfig.json` is strict mode. Block any `any` added in the PR diff. Pre-existing `any` in untouched lines is not a blocker.
*Cites: agent definition "TypeScript" section*

**16. Daily-page visual contract — no management actions on check-in cards.**
No `+`, `…`, `Manage`, `Add`, `Edit`, or `Archive` button anywhere on a `/checkin/[date]` card. Card header is `LABEL` + `TierPill` only. Notes is the sole exempt section. Block any violation of this.
*Cites: agent definition "Daily-page visual contract"*

**17. Recharts inline component ban.**
`react-hooks/static-components` rule fires when components are defined inside a render function. Any `const Foo = () => ...` inside a component body that renders Recharts or any JSX must be moved to module scope.

**18. `ResponsiveContainer` needs an explicit height.**
`<ResponsiveContainer>` without a parent height or explicit `height={...}` prop renders at 0px (invisible). Block chart components that don't establish height.

---

## Class-of-bug audit

When a finding matches one of these patterns, grep the full diff for siblings before reporting — these recur in clusters:

| Pattern | Risk | Where to grep |
|---|---|---|
| `field \|\| undefined` in PUT/PATCH body | Silently drops update for clearable fields | All mutation payload objects in `lib/api/hooks.ts` and inline fetch calls |
| `useEffect` dep array includes a `useMutation`-returned callback | Causes duplicate or infinite fires | Any `useEffect` with `mutate`/`mutation.mutate` in deps |
| `useState(loadX)` lazy initializer reading `localStorage` | SSR hydration mismatch | Any `'use client'` page with localStorage reads in state initializer |
| `col-span-*` on inner card inside sortable wrapper | 0-height ref node, wrong transform displacement | `components/checkin/cards/sortable-card.tsx` and siblings |
| `catch {}` or `catch (e) {}` with single generic toast | Masks 409/422 for investigation | All `try/catch` blocks in mutation handlers |

---

## Tier governance

Every check-in section belongs to exactly one tier. Assign before reviewing; if a card's tier is ambiguous, flag it.

| Tier | Examples | What user controls | Where managed |
|---|---|---|---|
| **Core** | Wellbeing, Gut, Bristol, Food | Show/hide only; labels immutable | `/customize/reorder` + `/customize/core-scales` (read-only) |
| **Catalog** | Supplements, Diet tags | Pick from DB list, request additions | `/customize/catalogs` |
| **Custom** | Trackers, Symptoms | Full CRUD: name, icon, archive, restore, reorder | `/customize/trackers`, `/customize/symptoms` |

Block if: a Core card gains an editable label, a daily-page card gains an inline `+` / `…` / `Manage`, a fourth tier is introduced, or archived items get a separate page.

Tier banner rule: every `/customize/*` detail screen opens with a tinted info card (zinc = Core, blue = Catalog, emerald = Custom) explaining that tier's freedoms in ≤50 words.

Archived items: collapsible section at the bottom of the same Custom detail screen. Never a separate route. Restore inline, no confirmation dialog.

---

## Input primitives — approved set

Use these and only these. Block new primitives without explicit approval.

1. Segmented scale (3–4 cells) — ordinal scales (wellbeing, sleep, stress, etc.)
2. 7-cell grid — fixed clinical scales (Bristol stool scale only)
3. Binary segmented (No/Yes) — yes-no trackers
4. Stepper — counter trackers (alcohol units, caffeine servings)
5. Pill multi-select — catalog-driven tag sets (supplements, diet tags)
6. Severity row (0–10) — symptom severity with inline chip expansion
7. Free text — Notes field

---

## Component architecture rules

- 150 lines max per file; split if exceeded
- Single Responsibility — one thing per component
- Co-locate route files: `page.tsx`, `loading.tsx`, `error.tsx` in the same folder
- Server Components by default; `'use client'` only for interactivity, browser APIs, or hooks
- Chrome from `@f0rge/ui` (Button, Card, Dialog, Accordion, Stepper, …). Labeled fields from `@f0rge/ui/forms`. Never copy primitives into `apps/**/components/ui`
- Props interface must be an explicit TypeScript interface (not inline type literal)
- `RowItem` primitive at `components/customize/row-item.tsx` — do not duplicate row anatomy elsewhere

---

## State management

- URL state first (`searchParams`) for filters and pagination
- Server state via TanStack Query v5 (`useQuery`/`useMutation`) — not raw `useEffect` fetches
- `useState` only for UI state (dropdowns, modals, form inputs)
- Lift state only as far as needed — not to a common ancestor "just in case"
- Prefer query prefix invalidation over per-key invalidation (see tracker archive pattern)

---

## Core-scales label accuracy

Labels in `app/customize/core-scales/page.tsx` must match the daily cards character-for-character. Verified correct values (2026-05-24):

| Scale | Options |
|---|---|
| "How was your day?" | Very Poor · Standard · Very Good |
| "Sleep quality (last night)" | Poor · OK · Good (NOT "Okay") |
| "Stress level" | Low · Medium · High (NOT "Med") |
| "Neuro symptoms" | Worse · Baseline · Better (NOT "Foggy") |
| "Stool" | Normal · Abnormal · Skipped (NOT "Off") |
| "Joint pain / crepitus" | None · Mild · Moderate · Severe |

Block any core-scales page change that diverges from the above without also updating the corresponding daily card.
*Cites: `frontend-dev/customize_hub_foundation.md`*

---

## What NOT to flag (false-positive suppression)

- `/icons/icon-192.png` 404 — PWA icon not deployed in dev
- `/api/v1/auth/me` 401 on first page load — expected before login
- `/api/v1/entries/{date}` 404 on today — editor falls back to create mode by design
- Reorder hub row has no `TierPill` — intentional; meta rows omit it (`tier` prop is optional on `HubRow`)
- Hero strip rendering 4 vs 5 tiles depending on whether a treatment is active — by design (`lg:grid-cols-4` vs `lg:grid-cols-5`)
- Bristol gate using caption + amber pill instead of amber ring — intentional UX decision
- `/checkin/{date}` is an editor; `/history/{date}` is a read-only summary — different pages, different affordances
- `comingSoon=true` rows on the Customize Hub with `opacity-50` — intentional roadmap placeholder, not dead UI

---

## Tone and output format

Return JSON:

```json
{
  "findings": [
    {
      "severity": "block | warn | nit",
      "file": "apps/marrow/frontend/components/...",
      "line": 42,
      "msg": "terse description of the violation",
      "cites": "frontend-dev/dnd_kit_grid_drag_reorder.md"
    }
  ],
  "summary": "one sentence"
}
```

- `block` = must fix before merge
- `warn` = strong preference, should fix
- `nit` = low-priority observation

Cite a memory file for every `block` finding. Be terse — no filler.
