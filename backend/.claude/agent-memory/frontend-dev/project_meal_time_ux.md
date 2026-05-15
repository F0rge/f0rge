---
name: meal time editing UX structure
description: How MealTimeChips is structured and where it appears
type: project
---

`MealTimeChips` (`frontend/components/checkin/meal-time-chips.tsx`) renders a horizontal pill row: `Now | 1h ago | 2h ago | 3h ago | Custom…`. Tapping a preset freezes a `new Date()` snapshot minus the offset at tap time (not relative to render). "Custom" reveals a native `<input type="time">` inline — chosen for simplicity over a full time-picker library.

The component shows the current `value` formatted as HH:MM next to the chips (inline when no custom input is open; beside the time input when custom is active). Active-chip highlighting is only applied to "Custom" button when that mode is open — offset presets don't track which was last selected (they're one-shot actions).

Appears in two places:
1. `photo-capture.tsx` — below each staged photo before upload.
2. `app/history/[date]/page.tsx` (`PhotoWithMealTime` component) — below each saved photo for in-place edit.

**Why:** Native `<input type="time">` was chosen over a library picker to keep the bundle small and match the mobile-native time picker on iOS/Android.
**How to apply:** If a full datetime picker is ever needed (not just time), reach for a shadcn-compatible library rather than extending this component.
