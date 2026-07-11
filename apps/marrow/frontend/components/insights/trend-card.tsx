'use client'

import { useState } from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import type { TrendSeries } from '@/lib/api/types'

interface Props {
  series: TrendSeries
}

function DeltaArrow({ delta }: { delta: number | null }) {
  if (delta === null) return <Minus className="size-3 text-muted-foreground" />
  if (delta > 0)
    return <TrendingUp className="size-3 text-green-600 dark:text-green-400" />
  if (delta < 0)
    return <TrendingDown className="size-3 text-red-600 dark:text-red-400" />
  return <Minus className="size-3 text-muted-foreground" />
}

function Sparkline({ points }: { points: TrendSeries['points'] }) {
  const data = points
    .filter((p) => p.value !== null)
    .slice(-30)
    .map((p) => ({ date: p.date, v: p.value }))

  if (data.length < 2) {
    return (
      <div className="flex h-10 items-center justify-center text-xs text-muted-foreground">
        not enough data
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={40}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="v"
          stroke="currentColor"
          strokeWidth={1.5}
          dot={false}
          className="text-primary"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

function FullChart({ series }: { series: TrendSeries }) {
  const data = series.points
    .filter((p) => p.value !== null || p.rolling_avg_7 !== null)
    .map((p) => ({
      date: p.date.slice(5), // MM-DD
      value: p.value,
      avg7: p.rolling_avg_7,
    }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10 }}
          interval="preserveStartEnd"
        />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          labelStyle={{ fontSize: 11 }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke="#6366f1"
          strokeWidth={1.5}
          dot={false}
          name="Value"
        />
        <Line
          type="monotone"
          dataKey="avg7"
          stroke="#94a3b8"
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 2"
          name="7-day avg"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function TrendCard({ series }: Props) {
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
        )}
      >
        <div className="mb-1 flex items-center justify-between gap-1">
          <span className="truncate text-xs font-medium text-card-foreground">
            {series.label}
          </span>
          <DeltaArrow delta={series.delta_30d} />
        </div>
        <Sparkline points={series.points} />
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-sm font-semibold tabular-nums">{currentDisplay}</span>
          <span className="text-xs text-muted-foreground">
            7d avg {avgDisplay}
          </span>
        </div>
      </DialogTrigger>

      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{series.label}</DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <FullChart series={series} />
        </div>
        <div className="flex gap-4 text-xs text-muted-foreground">
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
                  series.delta_30d > 0 && 'text-green-600',
                  series.delta_30d < 0 && 'text-red-600',
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
