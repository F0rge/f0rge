---
name: Obsidian renderer conventions
description: Key decisions and patterns in app/services/obsidian.py for the vault renderer
type: project
---

Vault renderer lives in `app/services/obsidian.py`. Key facts:

- **meal_time on photos**: rendered inline with the wikilink embed as `(HH:MM)` (24-hour, `strftime('%H:%M')`). Format: `![[attachments/filename.jpg]] (13:24)`. Guard `None` with a ternary — migration backfills from `created_at` so it will rarely be None in practice.

- **Omit-when-zero (alcohol/caffeine)**: `alcohol_units` and `caffeine_servings` on `Entry` are nullable. Leo's explicit preference: emit NOTHING in frontmatter or summary table when the value is `None` or `0`. When > 0, emit both the count key (`alcohol-units: N`) AND a boolean flag (`had-alcohol: true`) in frontmatter, plus a `| Alcohol | N unit(s) |` row in the summary table. Same pattern for caffeine.

- **Frontmatter order**: alcohol/caffeine keys are inserted between `hot-shower` and `active-treatments`. `active-treatments` always present.

- **Summary table order**: alcohol/caffeine rows appended after `| Logged at |` row, conditional on value > 0.

- **`getattr` defensive pattern**: use `getattr(entry, "field", None)` for new nullable columns throughout `_render_markdown` — consistent with existing `stool_status`, `bristol_type`, `entry_time`, etc.

**Why:** Omit-when-zero keeps vault diffs clean — days without alcohol/caffeine don't get noisy zero-value keys. Leo confirmed this pattern explicitly during Phase 2 of issue #35.

**How to apply:** Any future nullable boolean or count fields on `Entry` should follow the same omit-when-zero / emit-with-flag convention unless Leo specifies otherwise.
