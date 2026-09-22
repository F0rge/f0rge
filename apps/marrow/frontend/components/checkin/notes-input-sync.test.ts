import { describe, expect, it } from 'vitest'
import { shouldHydrateNotesDraft } from './notes-input-sync'

describe('shouldHydrateNotesDraft', () => {
  it('hydrates on first load when parent differs from draft', () => {
    expect(shouldHydrateNotesDraft(false, '', 'from server', '')).toBe(true)
  })

  it('ignores duplicate parent values', () => {
    expect(shouldHydrateNotesDraft(true, 'hello', 'hello', 'hello')).toBe(false)
  })

  it('ignores parent echoes while draft already matches', () => {
    expect(shouldHydrateNotesDraft(true, 'hello', 'hello', 'hell')).toBe(false)
  })

  it('accepts external parent updates after typing started', () => {
    expect(shouldHydrateNotesDraft(true, 'local draft', 'server notes', 'local draft')).toBe(true)
  })
})
