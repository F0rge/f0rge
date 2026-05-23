'use client'

/**
 * MiniBars — 7-bar CSS histogram. No Recharts.
 * Props:
 *   values     — array of up to 7 numbers (or null for missing days). Most-recent is LAST.
 *   colorClass — Tailwind class for the last bar (today's bar).
 *   maxOverride — optional explicit max. Defaults to max(values).
 */

interface MiniBarsProps {
  values: (number | null)[]
  colorClass: string
  maxOverride?: number
}

export function MiniBars({ values, colorClass, maxOverride }: MiniBarsProps) {
  const MAX_BARS = 7
  // Pad from the left with nulls if fewer than 7 values.
  const padded: (number | null)[] = Array(MAX_BARS - values.length)
    .fill(null)
    .concat(values)

  const maxVal = maxOverride ?? Math.max(...padded.filter((v): v is number => v !== null), 1)

  return (
    <div className="flex items-end gap-0.5 h-8" aria-hidden="true">
      {padded.map((v, i) => {
        const isToday = i === MAX_BARS - 1
        const heightPct = v !== null ? Math.max((v / maxVal) * 100, 4) : 0
        return (
          <div
            key={i}
            className={[
              'w-2 rounded-sm transition-all',
              v === null ? 'bg-transparent' : isToday ? colorClass : 'bg-stone-200 dark:bg-stone-600',
            ].join(' ')}
            style={{ height: v !== null ? `${heightPct}%` : '0%' }}
          />
        )
      })}
    </div>
  )
}
