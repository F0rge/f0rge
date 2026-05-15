---
name: Stepper component
description: Custom numeric stepper used for alcohol/caffeine counters
type: project
---

`<Stepper>` is at `frontend/components/ui/stepper.tsx`. Props: `value`, `onChange`, `min` (default 0), `max` (default 10), `label`, `tooltip` (optional). Layout: `[−] [n] [+]` using shadcn `Button` with `variant="outline" size="icon"` overridden to `size-11 rounded-lg` for mobile tap targets. Tooltip renders as a `<span title={tooltip}>` on the label plus a separate small text below.

Used in `checkin-form.tsx` in a two-column flex row for "Alcohol units" and "Caffeine servings", wrapped in a labeled card section between SupplementPicker and the BinaryInputs.

Entry type extended: `alcohol_units: number | null`, `caffeine_servings: number | null` on both `Entry` and `EntryCreate`. Submitted as integers in the PUT/POST body. Pre-filled from `existingEntry` on edit (defaults to 0 if null).

**Why:** Numeric stepper was custom-built because shadcn/ui has no native stepper primitive — kept thin and composable.
**How to apply:** Reuse for any 0–N integer field that benefits from tap-friendly +/− controls.
