import type { PhotoSignal } from '@/lib/api/types'

// Badge on each Diet risk pill. Matches the distinct ingredient names listed
// under the pills (`photo_signal.sources`). `histamine_load` is a dose sum of
// every confirmed score, including scores below the high-histamine threshold,
// so it is not a pill count.
export function dietFlagPillCount(flag: string, signal: PhotoSignal): number {
  return signal.sources[flag]?.length ?? 0
}
