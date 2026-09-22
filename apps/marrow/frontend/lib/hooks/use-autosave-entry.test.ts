import { describe, expect, it } from 'vitest'
import { recordBeaconCreateLocalState } from './use-autosave-entry'

describe('recordBeaconCreateLocalState', () => {
  it('marks the entry created and baselines serialized payload after beacon POST', () => {
    const entryCreatedRef = { current: false }
    const lastSerializedRef = { current: null as string | null }
    const serialized = '{"entry_date":"2025-09-22","wellbeing":3}'

    recordBeaconCreateLocalState(entryCreatedRef, lastSerializedRef, serialized)

    expect(entryCreatedRef.current).toBe(true)
    expect(lastSerializedRef.current).toBe(serialized)
  })
})
