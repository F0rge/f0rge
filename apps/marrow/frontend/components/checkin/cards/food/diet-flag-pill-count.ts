import type { PhotoSignal } from '@/lib/api/types'

// Badge on each Diet risk pill. Matches the distinct ingredient names listed
// under the pills (`photo_signal.sources`). `histamine_load` is a dose sum of
// every confirmed score, including scores below the high-histamine threshold,
// so it is not a pill count.
export function dietFlagPillCount(flag: string, signal: PhotoSignal): number {
  return signal.sources[flag]?.length ?? 0
}

// Header noun. Zero and every count other than 1 use the plural.
export function dietFlagIngredientLabel(count: number): string {
  return `${count} ${count === 1 ? 'flagged ingredient' : 'flagged ingredients'}`
}

// Header count. One ingredient listed under two flags counts once.
export function dietFlagIngredientCount(signal: PhotoSignal): number {
  const names = new Set<string>()
  for (const list of Object.values(signal.sources)) {
    for (const name of list) names.add(name)
  }
  return names.size
}
