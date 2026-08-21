'use client'

import { useState } from 'react'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  cn,
} from '@f0rge/ui'
import type { SignalsTrendSeries } from '@/lib/api/types/signals'
import { polarityTone } from './polarity'
import { TrendFullChart, TrendSparkline } from './trend-charts'

interface Props {
  series: SignalsTrendSeries
}

function DeltaArrow({
  delta,
  goodDirection,
}: {
  delta: number | null
  goodDirection: SignalsTrendSeries['good_direction']
}) {
  if (delta === null) return <Minus className="size-3 text-muted-foreground" />
  const tone = polarityTone(delta, goodDirection)
  if (delta > 0) return <TrendingUp className={cn('size-3', tone)} />
  if (delta < 0) return <TrendingDown className={cn('size-3', tone)} />
  return <Minus className="size-3 text-muted-foreground" />
}

export function SignalsTrendCard({ series }: Props) {
  const [open, setOpen] = useState(false)
  const currentDisplay =
    series.current !== null ? series.current.toFixed(1) : '—'
  const avgDisplay =
    series.rolling_avg_7 !== null ? series.rolling_avg_7.toFixed(1) : '—'

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={cn(
          'w-full rounded-xl bg-card p-3 text-left ring-1 ring-foreground/10',
          'transition-colors hover:bg-muted/40 active:bg-muted/60',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <div className="mb-1 flex items-center justify-between gap-1">
          <span className="truncate text-xs font-medium text-card-foreground">
            {series.label}
          </span>
          <span className="flex shrink-0 items-center gap-1">
            {series.delta_30d !== null && (
              <span
                className={cn(
                  'text-[10px] tabular-nums',
                  polarityTone(series.delta_30d, series.good_direction),
                )}
              >
                {series.delta_30d > 0 ? '+' : ''}
                {series.delta_30d.toFixed(1)}
              </span>
            )}
            <DeltaArrow delta={series.delta_30d} goodDirection={series.good_direction} />
          </span>
        </div>
        <TrendSparkline points={series.points} />
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-sm font-semibold tabular-nums">{currentDisplay}</span>
          <span className="text-xs text-muted-foreground">7d avg {avgDisplay}</span>
        </div>
      </DialogTrigger>

      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{series.label}</DialogTitle>
        </DialogHeader>
        <div className="mt-2" aria-label={`${series.label} trend chart`}>
          <TrendFullChart series={series} />
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span>
            Current: <strong className="text-foreground">{currentDisplay}</strong>
          </span>
          <span>
            7d avg: <strong className="text-foreground">{avgDisplay}</strong>
          </span>
          {series.delta_30d !== null && (
            <span>
              30d delta:{' '}
              <strong
                className={cn(
                  'text-foreground',
                  polarityTone(series.delta_30d, series.good_direction),
                )}
              >
                {series.delta_30d > 0 ? '+' : ''}
                {series.delta_30d.toFixed(2)}
              </strong>
            </span>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
