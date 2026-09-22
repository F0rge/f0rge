import { describe, expect, it } from 'vitest'
import { shouldApplyEntryHydration } from './checkin-board-entry-sync'

describe('shouldApplyEntryHydration', () => {
  it('applies server entry on first load when the board is clean', () => {
    expect(shouldApplyEntryHydration(false)).toBe(true)
  })

  it('skips server entry while local edits are in progress', () => {
    expect(shouldApplyEntryHydration(true)).toBe(false)
  })
})
