import type { CardId } from './card-order'

/** Preferred desktop (lg+) column span per card before row-fill expansion. */
const PREFERRED_LG_SPAN: Record<CardId, number> = {
  food: 12,
  wellbeing: 4,
  gut: 4,
  supplements: 4,
  medications: 6,
  symptoms: 6,
  trackers: 6,
  notes: 12,
}

function colSpanClass(span: number): string {
  if (span >= 12) return 'col-span-12'
  return `col-span-12 lg:col-span-${span}`
}

/**
 * Compute responsive grid column spans for visible check-in cards.
 *
 * On desktop, cards are packed into 12-column rows using each card's preferred
 * span. Leftover space in a row is given to the last card so lone half-width
 * cards (e.g. trackers when notes is full-width) expand to fill the row.
 */
export function computeCardColSpans(visibleIds: CardId[]): Record<CardId, string> {
  const result = {} as Record<CardId, string>
  let row: CardId[] = []
  let rowWidth = 0

  const flushRow = () => {
    if (row.length === 0) return
    const spans = row.map((id) => PREFERRED_LG_SPAN[id])
    const totalPreferred = spans.reduce((sum, span) => sum + span, 0)
    const leftover = 12 - totalPreferred
    if (leftover > 0) {
      spans[spans.length - 1] += leftover
    }
    row.forEach((id, i) => {
      result[id] = colSpanClass(spans[i])
    })
    row = []
    rowWidth = 0
  }

  for (const id of visibleIds) {
    const pref = PREFERRED_LG_SPAN[id]
    if (rowWidth > 0 && rowWidth + pref > 12) {
      flushRow()
    }
    row.push(id)
    rowWidth += pref
    if (rowWidth >= 12) {
      flushRow()
    }
  }

  flushRow()
  return result
}
