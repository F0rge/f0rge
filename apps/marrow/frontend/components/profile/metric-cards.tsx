'use client'

import { Triangle } from 'lucide-react'
import { cn, formatLocalDate } from '@f0rge/ui'
import { useInsightsTrends } from '@/lib/api/hooks'
import type { TrendSeries } from '@/lib/api/types'

// Which series earn a card, and which way is "better" — the product decision.
const METRICS: { key: string; unit: string; downIsGood: boolean }[] = [
  { key: 'overall', unit: '/ 5', downIsGood: false },
  { key: 'sleep_quality', unit: '/ 5', downIsGood: false },
  { key: 'stress', unit: '/ 5', downIsGood: true },
  { key: 'bloating', unit: '/ 3', downIsGood: true },
  { key: 'hm_resting_hr', unit: 'bpm', downIsGood: true },
]

const FLAT_DELTA = 0.05 // below this, the week didn't really move
const MIN_PRIOR_DAYS = 3 // a delta off 1–2 logged days is noise, not a trend
const MIN_SPARK_POINTS = 3

function localDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return formatLocalDate(d)
}

function values(points: TrendSeries['points']): number[] {
  return points.flatMap((p) => (p.value == null ? [] : [p.value]))
}

/** Callers must reject empty input first — the mean of nothing is NaN. */
function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length
}

/** Hand-rolled 52×16 sparkline — a fortnight of points doesn't need a chart lib. */
function Sparkline({ xs }: { xs: number[] }) {
  const min = Math.min(...xs)
  const span = Math.max(...xs) - min
  const coords = xs.map((v, i): [number, number] => [
    2 + (i / (xs.length - 1)) * 48,
    // A flat series has no range to normalise against — draw it down the middle.
    span === 0 ? 8 : 14 - ((v - min) / span) * 12,
  ])
  const [lastX, lastY] = coords[coords.length - 1]

  return (
    <svg viewBox="0 0 52 16" className="mt-2 h-4 w-[52px]" aria-hidden>
      <polyline
        points={coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')}
        fill="none"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="stroke-muted-foreground"
      />
      <circle cx={lastX} cy={lastY} r="2" style={{ fill: 'var(--marrow-nucleus)' }} />
    </svg>
  )
}

function Delta({ delta, downIsGood }: { delta: number; downIsGood: boolean }) {
  const flat = Math.abs(delta) < FLAT_DELTA
  const down = delta < 0
  // Sign picks the arrow, polarity picks the colour: falling stress is a win, falling sleep isn't.
  const improving = down === downIsGood
  const magnitude = Math.abs(delta).toFixed(1)
  const tone = flat
    ? 'text-muted-foreground'
    : improving
      ? 'text-emerald-600 dark:text-emerald-400'
      : 'text-destructive'

  return (
    // role="img" — a bare aria-label on a <p> doesn't announce.
    <p
      role="img"
      aria-label={
        flat
          ? 'no change vs last week'
          : `${down ? 'down' : 'up'} ${magnitude} vs last week, ${improving ? 'improving' : 'worsening'}`
      }
      className={cn('mt-1.5 flex items-center gap-0.5 text-[10px] font-semibold tabular-nums', tone)}
    >
      {flat ? (
        '—'
      ) : (
        <>
          <Triangle
            className={cn('size-2', down && 'rotate-180')}
            fill="currentColor"
            strokeWidth={0}
            aria-hidden
          />
          {magnitude}
        </>
      )}
    </p>
  )
}

export function MetricCards() {
  // 14 dense days (the backend pads every date in the range), so within each series
  // the last 7 points are this week and the first 7 are the week to measure it against.
  const trends = useInsightsTrends(localDaysAgo(13), localDaysAgo(0))
  const series = trends.data?.series ?? []

  const cards = METRICS.flatMap(({ key, unit, downIsGood }) => {
    const match = series.find((s) => s.key === key)
    if (match == null) return []
    const recent = values(match.points.slice(-7))
    if (recent.length === 0) return []
    const prior = values(match.points.slice(0, 7))
    const thisWeek = mean(recent)
    return [
      {
        key,
        unit,
        downIsGood,
        label: match.label,
        value: Math.round(thisWeek * 10) / 10,
        delta: prior.length >= MIN_PRIOR_DAYS ? thisWeek - mean(prior) : null,
        spark: values(match.points),
      },
    ]
  })

  if (cards.length === 0) return null

  return (
    <section aria-label="Metric trends" className="flex gap-2 overflow-x-auto pb-1">
      {cards.map((c) => (
        <div
          key={c.key}
          className="w-[118px] flex-none rounded-xl bg-card p-3 ring-1 ring-foreground/10"
        >
          <p className="truncate text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            {c.label}
          </p>
          <p className="mt-1 flex items-baseline gap-1">
            <span className="text-[19px] font-bold leading-none tabular-nums">{c.value}</span>
            <span className="text-[10px] text-muted-foreground">{c.unit}</span>
          </p>
          {c.delta !== null && <Delta delta={c.delta} downIsGood={c.downIsGood} />}
          {c.spark.length >= MIN_SPARK_POINTS && <Sparkline xs={c.spark} />}
        </div>
      ))}
    </section>
  )
}
