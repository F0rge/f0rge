import { describe, expect, it } from 'vitest'
import { formatWaterfallNumber } from './waterfall-row'

describe('formatWaterfallNumber', () => {
  it('rounds unsigned IEEE leftovers to one decimal', () => {
    expect(formatWaterfallNumber(1.19999999999)).toBe('1.2')
    expect(formatWaterfallNumber(1.1 + 0.1)).toBe('1.2')
  })

  it('keeps a leading plus on signed non-negative values', () => {
    expect(formatWaterfallNumber(0.2, true)).toBe('+0.2')
    expect(formatWaterfallNumber(0, true)).toBe('+0.0')
  })

  it('keeps the minus from toFixed on signed negatives', () => {
    expect(formatWaterfallNumber(-0.4, true)).toBe('-0.4')
  })
})
