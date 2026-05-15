---
name: photo upload and meal time pattern
description: How photo state is managed across check-in form and how meal_time is passed to the API
type: project
---

Photos in the check-in flow use parallel arrays managed in `checkin-form.tsx`: `photos: File[]`, `labels: string[]`, `mealTimes: (Date | null)[]`. All three arrays are kept in sync — add/remove always operates on all three together in `photo-capture.tsx`.

`useUploadPhoto` in `hooks.ts` accepts an optional `mealTime: Date | null` and calls `.toISOString()` before appending to FormData as `meal_time`. The backend `POST /api/v1/entries/{date}/photos` accepts this as a Form field.

For history-page edits: `useUpdatePhotoMealTime` calls `PATCH /api/v1/photos/{id}` with `{ meal_time: "<ISO 8601>" }`. The `PhotoWithMealTime` component in `app/history/[date]/page.tsx` holds optimistic local state via `useState<string | null>` seeded from `photo.meal_time`.

`Photo` type now includes `meal_time: string | null`.

**Why:** The parallel-array approach was already established for photos/labels — extending it to mealTimes avoids a refactor to objects.
**How to apply:** Any future per-photo metadata should follow the same parallel-array pattern until a photo object model refactor is warranted.
