import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defaultMealTimeForEntry, entryLocalDate } from './meal-time'

describe('meal-time', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-22T15:30:45.123'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('parses entry date at local midnight', () => {
    const d = entryLocalDate('2026-09-10')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(8)
    expect(d.getDate()).toBe(10)
    expect(d.getHours()).toBe(0)
    expect(d.getMinutes()).toBe(0)
  })

  it('anchors default meal time on the entry day with today clock', () => {
    const d = defaultMealTimeForEntry('2026-09-10')
    expect(d.getFullYear()).toBe(2026)
    expect(d.getMonth()).toBe(8)
    expect(d.getDate()).toBe(10)
    expect(d.getHours()).toBe(15)
    expect(d.getMinutes()).toBe(30)
    expect(d.getSeconds()).toBe(45)
  })
})
