'use client'

import Link from 'next/link'
import { cn } from '@f0rge/ui'
import type { SignalsToday } from '@/lib/api/types/signals'
import { polarityFill, polarityTone } from './polarity'
import { formatWaterfallNumber, WaterfallRow } from './waterfall-row'

interface Props {
  today: SignalsToday
  goodDirection: 'up' | 'down' | null
}

export function TodayWaterfall({ today, goodDirection }: Props) {
  const contributions = today.contributions ?? []
  const maxAbs = Math.max(
    Math.abs(today.baseline ?? 0),
    ...contributions.map((c) => Math.abs(c.display_value)),
    0.01,
  )

  const predicted = today.predicted
  const actual = today.actual
  const residual = today.residual

  let residualCopy: string | null = null
  if (actual != null && predicted != null) {
    if (actual < predicted) {
      residualCopy = 'Today came in below the model prediction.'
    } else if (actual > predicted) {
      residualCopy = 'Today came in above the model prediction.'
    } else {
      residualCopy = 'Today matched the model prediction.'
    }
  }

  if (today.baseline == null && predicted == null && contributions.length === 0) {
    return (
      <section aria-label="Today's prediction breakdown" className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Waterfall
        </h2>
        <p className="text-sm text-muted-foreground">
          No check-in for today yet.{' '}
          <Link
            href="/checkin"
            className="font-medium text-foreground underline-offset-4 hover:underline"
          >
            Log a check-in
          </Link>
        </p>
      </section>
    )
  }

  return (
    <section aria-label="Today's prediction breakdown" className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Waterfall
      </h2>
      <div className="space-y-2 rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        {today.baseline != null && (
          <WaterfallRow
            label="Baseline"
            value={today.baseline}
            barWidth={(Math.abs(today.baseline) / maxAbs) * 50}
            signed={false}
          />
        )}
        {contributions.map((c) => (
          <WaterfallRow
            key={c.driver_id}
            label={c.label}
            value={c.display_value}
            detail={c.detail}
            tone={polarityTone(c.display_value, goodDirection)}
            barWidth={(Math.abs(c.display_value) / maxAbs) * 50}
            barClass={polarityFill(c.display_value, goodDirection)}
          />
        ))}
        {predicted != null && (
          <div className="border-t border-border pt-2">
            <WaterfallRow label="Predicted" value={predicted} signed={false} />
          </div>
        )}
        {actual != null && (
          <WaterfallRow
            label="Actual"
            value={actual}
            signed={false}
            tone={residual != null ? polarityTone(residual, goodDirection) : undefined}
          />
        )}
        {residual != null && (
          <p className={cn('text-xs', polarityTone(residual, goodDirection))}>
            Residual {formatWaterfallNumber(residual, true)}
            {residualCopy ? ` — ${residualCopy}` : null}
          </p>
        )}
        {today.band_low != null && today.band_high != null && (
          <p className="text-xs text-muted-foreground">
            Band {formatWaterfallNumber(today.band_low)} –{' '}
            {formatWaterfallNumber(today.band_high)}
            {today.band_level != null ? ` (level ${today.band_level})` : null}
          </p>
        )}
      </div>
    </section>
  )
}
