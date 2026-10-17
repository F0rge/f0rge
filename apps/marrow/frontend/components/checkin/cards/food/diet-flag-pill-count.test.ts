import { describe, expect, it } from 'vitest'

import { dietFlagIngredientCount, dietFlagPillCount } from './diet-flag-pill-count'
import type { PhotoSignal } from '@/lib/api/types'

// 2026-10-17 check-in: coffee with oat milk + H3 carbonara.
// histamine_load is coffee 1 + spaghetti 1 + bacon 3 + parmesan 3 = 8.
// The source line lists only the two ingredients at or above the threshold.
const october17: PhotoSignal = {
  flags: ['high-fodmap', 'dairy', 'gluten', 'high-histamine'],
  scores: {
    histamine_load: 8,
    fodmap_count: 1,
    gluten_count: 1,
    dairy_count: 2,
  },
  sources: {
    'high-fodmap': ['spaghetti'],
    dairy: ['parmesan', 'cream'],
    gluten: ['spaghetti'],
    'high-histamine': ['bacon', 'parmesan'],
  },
}

describe('dietFlagPillCount', () => {
  it('counts distinct listed ingredients, not the histamine score sum', () => {
    expect(dietFlagPillCount('high-histamine', october17)).toBe(2)
    expect(dietFlagPillCount('high-histamine', october17)).not.toBe(
      october17.scores.histamine_load,
    )
  })

  it('uses the same distinct-name count for every flag', () => {
    expect(dietFlagPillCount('high-fodmap', october17)).toBe(1)
    expect(dietFlagPillCount('dairy', october17)).toBe(2)
    expect(dietFlagPillCount('gluten', october17)).toBe(1)
  })

  it('follows the source list when a row count is higher', () => {
    const signal: PhotoSignal = {
      flags: ['gluten'],
      scores: {
        histamine_load: 0,
        fodmap_count: 0,
        gluten_count: 2,
        dairy_count: 0,
      },
      sources: { gluten: ['bread'] },
    }
    expect(dietFlagPillCount('gluten', signal)).toBe(1)
  })

  it('is zero when a flag has no listed ingredients', () => {
    expect(dietFlagPillCount('high-histamine', { ...october17, sources: {} })).toBe(0)
  })
})

describe('dietFlagIngredientCount', () => {
  it('counts each listed name once across flags', () => {
    // Per-flag lengths are 1 + 2 + 1 + 2 = 6. Distinct names are 4.
    expect(dietFlagIngredientCount(october17)).toBe(4)
    expect(dietFlagIngredientCount(october17)).not.toBe(6)
  })

  it('is zero when nothing is listed', () => {
    expect(dietFlagIngredientCount({ ...october17, sources: {} })).toBe(0)
  })
})
