# Vision catalog context — expected match-rate lift (#334)

Fixture notes for PR review. **Not live OpenRouter runs** — mapping is derived from
`IngredientLookupService` chain (exact canonical → alias → head-noun → ILIKE) and seed
aliases in `scripts/build_aliases.py` (`coriander`→`cilantro`, bell-pepper colour variants).

Pytest (`tests/test_vision_catalog.py`) covers orchestrator wiring with a mocked LLM; these
scenarios document the **lookup null-count delta** reviewers should expect on real photos.

**Catalog prompt cost:** seed catalog (~287 entries) adds ~2–4k tokens to the system prompt
(soft cap 500 lines in `catalog_context.py`).

---

## Scenario A — Cilantro-heavy pico (tacos / salsa garnish)

Photo shows chopped green herb, tomato, onion, lime wedge. User catalog includes
`cilantro [aliases: coriander]`, `tomato`, `onion`, `lime`.

| # | Blind `name` (no catalog) | Catalog-aware `name` | `lookup()` blind | `lookup()` catalog-aware |
|---|---------------------------|----------------------|------------------|--------------------------|
| 1 | coriander garnish | cilantro | **null** (compound; no alias) | cilantro ✓ |
| 2 | diced tomato | tomato | tomato ✓ (head-noun) | tomato ✓ |
| 3 | white onion | onion | onion ✓ (head-noun) | onion ✓ |
| 4 | lime wedge | lime | **null** (head-noun `wedge`) | lime ✓ |

**`canonical_name` nulls:** 2 / 4 blind → **0 / 4** catalog-aware (−2).

*Note:* blind `coriander` alone would resolve via alias, but vision often emits garnish
phrases; catalog context steers the model to the tracked canonical `cilantro`.

---

## Scenario B — Bell-pepper fajita bowl

Photo shows sautéed pepper strips, onion, chicken, spice. User catalog includes
`bell pepper` (with `red bell pepper`, `green pepper`, … aliases from seed), `onion`,
`chicken`, `cumin`.

| # | Blind `name` (no catalog) | Catalog-aware `name` | `lookup()` blind | `lookup()` catalog-aware |
|---|---------------------------|----------------------|------------------|--------------------------|
| 1 | pepper strips | red bell pepper | **null** (head-noun `strips`) | bell pepper ✓ (alias) |
| 2 | sliced onion | onion | onion ✓ (head-noun) | onion ✓ |
| 3 | chicken thigh | chicken | **null** (head-noun `thigh`) | chicken ✓ |
| 4 | cumin | cumin | cumin ✓ | cumin ✓ |

**`canonical_name` nulls:** 2 / 4 blind → **0 / 4** catalog-aware (−2).

*Note:* blind `pepper` or `green pepper` often resolve (ILIKE / alias), but strip/slice
phrasing is common on fajita photos and misses without catalog-aligned naming.

---

## Summary

| Scenario | Ingredients | Blind nulls | Catalog-aware nulls | Δ |
|----------|-------------|-------------|---------------------|---|
| A — cilantro pico | 4 | 2 | 0 | −2 |
| B — bell-pepper fajita | 4 | 2 | 0 | −2 |

Combined fixture expectation: **4 fewer null `canonical_name` values** across these two
meals (50% → 0% on tracked ingredients).
