/**
 * feature-flag.ts — localStorage toggle for the V2 cards layout.
 *
 * Key: 'ht.cards-v2'
 * Default: true (ON) — switch to false to fall back to the old single-column form.
 *
 * Usage in page.tsx:
 *   const v2 = readCardsV2()
 *   return v2 ? <CheckinBoard ... /> : <CheckinForm ... />
 *
 * This file is deleted when the flag flip is permanent (final PR commit).
 */

const KEY = 'ht.cards-v2'

export function readCardsV2(): boolean {
  if (typeof window === 'undefined') return true
  const stored = window.localStorage.getItem(KEY)
  // Default ON — 'false' is the opt-out value.
  return stored !== 'false'
}

export function setCardsV2(enabled: boolean): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(KEY, enabled ? 'true' : 'false')
}
