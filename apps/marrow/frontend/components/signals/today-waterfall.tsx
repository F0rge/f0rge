'use client'

import { cn } from '@f0rge/ui'
import type { SignalsToday } from '@/lib/api/types/signals'
import { polarityTone } from './polarity'

interface Props {
  today: SignalsToday
  goodDirection: 'up' | 'down' | null
}

function WaterfallRow({
  label,
  value,
  detail,
  tone,
  barWidth,
}: {
  label: string
  value: number
  detail?: string | null
  tone?: string
  barWidth?: number
}) {
  const signed = value >= 0 ? `+${value}` : String(value)
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 shrink-0 truncate text-muted-foreground">{label}</span>
      <div className="relative h-5 min-w-0 flex-1 rounded bg-muted/50">
        {barWidth != null && barWidth > 0 && (
          <div
            className={cn(
              'absolute top-0 h-full rounded',
              value >= 0 ? 'left-1/2 bg-emerald-500/70' : 'right-1/2 bg-red-500/70',
            )}
            style={{ width: `${barWidth}%` }}
          />
        )}
      </div>
      <span className={cn('w-14 shrink-0 text-right tabular-nums', tone)}>
        {signed}
      </span>
      {detail ? (
        <span className="hidden truncate text-xs text-muted-foreground sm:inline">
          {detail}
        </span>
      ) : null}
    </div>
  )
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
          />
        ))}
        {predicted != null && (
          <div className="border-t border-border pt-2">
            <WaterfallRow label="Predicted" value={predicted} />
          </div>
        )}
        {actual != null && (
          <WaterfallRow
            label="Actual"
            value={actual}
            tone={residual != null ? polarityTone(residual, goodDirection) : undefined}
          />
        )}
        {residual != null && (
          <p className={cn('text-xs', polarityTone(residual, goodDirection))}>
            Residual {residual >= 0 ? '+' : ''}
            {residual}
            {residualCopy ? ` — ${residualCopy}` : null}
          </p>
        )}
        {today.band_low != null && today.band_high != null && (
          <p className="text-xs text-muted-foreground">
            Band {today.band_low} – {today.band_high}
            {today.band_level != null ? ` (level ${today.band_level})` : null}
          </p>
        )}
      </div>
    </section>
  )
}
