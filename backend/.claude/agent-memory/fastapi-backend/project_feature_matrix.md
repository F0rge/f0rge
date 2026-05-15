---
name: Feature matrix column conventions
description: STATIC_COLUMNS ordering, derived column encoding, and null-row behaviour in feature_matrix.py
type: project
---

## Column ordering in STATIC_COLUMNS

Insertion point for new entry-level fields: immediately after `hot_shower`, before `stool_status`. This keeps lifestyle/exposure fields grouped together. Pattern established in Phase 3 (issue #35): alcohol_units → caffeine_servings → had_alcohol → had_caffeine.

## Derived boolean columns

Derived booleans are encoded as **0/1 integers** (not Python `True`/`False`). The raw ORM boolean fields (`sick`, `hot_shower`) stay as native Python bools. Derived fields computed from nullable int columns use the pattern:

```python
row["had_X"] = 1 if (entry.x or 0) > 0 else 0
```

`or 0` handles `None` (treats it as 0), so `had_X` is always 0 when the raw value is None or 0.

## Null-row behaviour

Rows for dates with no Entry are pre-filled with `None` for all columns (including derived ones). Derived columns are only populated inside `if entry is not None:`. This means `had_alcohol` and `had_caffeine` are `None` on entry-less dates — not 0. Tests must assert `is None` for those cases, not `== 0`.

## per-photo meal_time

`Photo.meal_time` was added in Phase 1 but intentionally excluded from the feature matrix. It's per-photo and intended for future lag-analysis work. The per-day export does not aggregate it.

**Why:** The feature matrix is one-row-per-day; meal_time is per-photo. Aggregating it (min/max/first) would require a design decision not yet made.

**How to apply:** Do not add meal_time columns to STATIC_COLUMNS without a separate design discussion.
