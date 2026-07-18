import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import {
  DEFAULT_CARD_ORDER,
  loadCardOrder,
  loadHiddenCards,
  saveCardOrder,
  hasCustomOrder,
  type CardId,
} from './card-order'

describe('card-order', () => {
  const storage = new Map<string, string>()

  beforeEach(() => {
    storage.clear()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value)
      },
      removeItem: (key: string) => {
        storage.delete(key)
      },
    })
    vi.stubGlobal('window', { localStorage: globalThis.localStorage })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns default order when localStorage is empty', () => {
    expect(loadCardOrder()).toEqual([...DEFAULT_CARD_ORDER])
  })

  it('filters unknown card ids and appends missing defaults', () => {
    storage.set('ht.cards-v2.order', JSON.stringify(['notes', 'food', 'removed-card']))
    expect(loadCardOrder()).toEqual([
      'notes',
      'food',
      'wellbeing',
      'gut',
      'supplements',
      'medications',
      'symptoms',
      'trackers',
    ])
  })

  it('persists custom order', () => {
    const custom: CardId[] = [
      'notes',
      'food',
      'wellbeing',
      'gut',
      'supplements',
      'medications',
      'symptoms',
      'trackers',
    ]
    saveCardOrder(custom)
    expect(loadCardOrder()).toEqual(custom)
    expect(hasCustomOrder()).toBe(true)
  })

  it('loadHiddenCards returns empty on corrupt data', () => {
    storage.set('ht.cards-v2.hidden', 'not-json')
    expect(loadHiddenCards()).toEqual([])
  })
})
