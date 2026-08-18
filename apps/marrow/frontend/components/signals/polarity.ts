import type { GoodDirection } from '@/lib/api/types/signals'
import { statusText } from '@/lib/ui/status'

const FLAT_DELTA = 0.05

/** Whether a signed delta moves in the good direction. */
export function deltaIsGood(delta: number, goodDirection: GoodDirection): boolean | null {
  if (goodDirection === null || Math.abs(delta) < FLAT_DELTA) return null
  if (goodDirection === 'up') return delta > 0
  if (goodDirection === 'down') return delta < 0
  return null
}

export function polarityTone(delta: number, goodDirection: GoodDirection): string {
  const good = deltaIsGood(delta, goodDirection)
  if (good === null) return 'text-muted-foreground'
  return good ? statusText.ok : statusText.destructive
}

export function crossesZero(ciLow: number | null, ciHigh: number | null): boolean {
  if (ciLow === null || ciHigh === null) return false
  return ciLow <= 0 && ciHigh >= 0
}
