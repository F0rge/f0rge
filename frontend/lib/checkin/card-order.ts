/**
 * card-order.ts — localStorage persistence for check-in card order.
 *
 * SSR-safe (all localStorage access guarded by typeof window check).
 */

const STORAGE_KEY = 'ht.cards-v2.order'

export type CardId =
  | 'food'
  | 'insights'
  | 'wellbeing'
  | 'gut'
  | 'supplements'
  | 'symptoms'
  | 'trackers'
  | 'notes'

export const DEFAULT_CARD_ORDER: readonly CardId[] = [
  'food',
  'insights',
  'wellbeing',
  'gut',
  'supplements',
  'symptoms',
  'trackers',
  'notes',
]

const KNOWN_IDS = new Set<string>(DEFAULT_CARD_ORDER)

/**
 * Load the saved order from localStorage.
 *
 * - Filters out any unknown IDs (removed cards).
 * - Appends any default IDs not present (newly added cards).
 * - Returns DEFAULT_CARD_ORDER on any error, missing key, or SSR.
 */
export function loadCardOrder(): CardId[] {
  if (typeof window === 'undefined') return [...DEFAULT_CARD_ORDER]

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return [...DEFAULT_CARD_ORDER]

    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return [...DEFAULT_CARD_ORDER]

    const filtered = parsed.filter(
      (id): id is CardId => typeof id === 'string' && KNOWN_IDS.has(id),
    )

    // Append any default IDs that are missing from saved order.
    for (const id of DEFAULT_CARD_ORDER) {
      if (!filtered.includes(id)) filtered.push(id)
    }

    return filtered
  } catch {
    return [...DEFAULT_CARD_ORDER]
  }
}

export function saveCardOrder(order: CardId[]): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEY, JSON.stringify(order))
}

export function resetCardOrder(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEY)
}

/** Returns true when a custom (non-default) order is currently saved. */
export function hasCustomOrder(): boolean {
  if (typeof window === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) !== null
}
