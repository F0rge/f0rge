/**
 * card-order.ts — localStorage persistence for check-in card order and visibility.
 *
 * SSR-safe (all localStorage access guarded by typeof window check).
 */

const STORAGE_KEY = 'ht.cards-v2.order'
const HIDDEN_KEY = 'ht.cards-v2.hidden'
const COLLAPSED_KEY = 'ht.cards-v2.collapsed'

export type CardId =
  | 'food'
  | 'wellbeing'
  | 'gut'
  | 'supplements'
  | 'medications'
  | 'symptoms'
  | 'trackers'
  | 'notes'

/** Cards that support on-page collapse (includes pinned Protocol). */
export type CollapseId = CardId | 'protocol'

export const DEFAULT_CARD_ORDER: readonly CardId[] = [
  'food',
  'wellbeing',
  'gut',
  'supplements',
  'medications',
  'symptoms',
  'trackers',
  'notes',
]

const KNOWN_COLLAPSE_IDS = new Set<string>([...DEFAULT_CARD_ORDER, 'protocol'])

const KNOWN_IDS = new Set<string>(DEFAULT_CARD_ORDER)

/**
 * Load the saved order from localStorage.
 *
 * - Filters out any unknown IDs (removed cards, e.g. 'insights' from pre-2026-05 saves).
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
    // Intentional swallow: corrupt/foreign localStorage value falls back to
    // the default order silently. A toast here would fire on every page load
    // for any user with a stale/malformed save — not a mutation the user
    // triggered, so there's nothing actionable to surface.
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

// ── Hidden cards ─────────────────────────────────────────────────────────────

/**
 * Load the set of hidden card IDs from localStorage.
 *
 * - Filters to only known IDs so stale saves don't include removed cards.
 * - Returns [] on any error, missing key, or SSR.
 */
export function loadHiddenCards(): CardId[] {
  if (typeof window === 'undefined') return []

  try {
    const raw = localStorage.getItem(HIDDEN_KEY)
    if (!raw) return []

    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    return parsed.filter(
      (id): id is CardId => typeof id === 'string' && KNOWN_IDS.has(id),
    )
  } catch {
    // Intentional swallow — same reasoning as loadCardOrder above.
    return []
  }
}

export function saveHiddenCards(hidden: CardId[]): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(HIDDEN_KEY, JSON.stringify(hidden))
}

export function resetHiddenCards(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(HIDDEN_KEY)
}

/** Returns true when at least one card is currently hidden. */
export function hasHiddenCards(): boolean {
  if (typeof window === 'undefined') return false
  const raw = localStorage.getItem(HIDDEN_KEY)
  if (!raw) return false
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) && parsed.length > 0
  } catch {
    // Intentional swallow — same reasoning as loadCardOrder above.
    return false
  }
}

// ── Collapsed cards (on-page hide, distinct from customize hidden) ───────────

export function loadCollapsedCards(): CollapseId[] {
  if (typeof window === 'undefined') return []

  try {
    const raw = localStorage.getItem(COLLAPSED_KEY)
    if (!raw) return []

    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    return parsed.filter(
      (id): id is CollapseId => typeof id === 'string' && KNOWN_COLLAPSE_IDS.has(id),
    )
  } catch {
    return []
  }
}

export function saveCollapsedCards(collapsed: CollapseId[]): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(COLLAPSED_KEY, JSON.stringify(collapsed))
}

export function toggleCollapsedCard(collapsed: CollapseId[], id: CollapseId): CollapseId[] {
  return collapsed.includes(id)
    ? collapsed.filter((c) => c !== id)
    : [...collapsed, id]
}
