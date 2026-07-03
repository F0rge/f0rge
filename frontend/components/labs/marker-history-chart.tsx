'use client'

import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Dot,
} from 'recharts'
import { Loader2, Pin, PinOff } from 'lucide-react'
import { useMarkerHistory, useTreatments } from '@/lib/api/hooks'
import type { MarkerFlag } from '@/lib/api/types'

interface MarkerHistoryChartProps {
  canonicalName: string
  displayName?: string
}

const FLAG_COLORS: Record<MarkerFlag, string> = {
  normal: '#6366f1',
  low: '#3b82f6',
  high: '#ef4444',
  abnormal: '#f59e0b',
  unknown: '#94a3b8',
}

const PINNED_KEY = 'labs.pinnedMarkers'

function getPinned(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    // Intentional swallow: corrupt localStorage value just means "no pins
    // yet" — not a mutation the user triggered, nothing to toast.
    return []
  }
}

function setPinned(list: string[]) {
  try {
    localStorage.setItem(PINNED_KEY, JSON.stringify(list))
  } catch {
    // Intentional swallow: storage full/disabled (e.g. private browsing).
    // Pin state is a nice-to-have preference, not worth interrupting the
    // user with a toast over.
  }
}

function computeRefBand(
  points: { ref_low: number | null; ref_high: number | null }[],
  yMin: number,
  yMax: number,
): { low: number | null; high: number | null } {
  // Collect non-null ref values across series
  const lows = points.map((p) => p.ref_low).filter((v): v is number => v !== null)
  const highs = points.map((p) => p.ref_high).filter((v): v is number => v !== null)
  const low = lows.length > 0 ? Math.min(...lows) : null
  const high = highs.length > 0 ? Math.max(...highs) : null

  if (low === null && high === null) return { low: null, high: null }
  // Half-bands: use chart domain edge when only one bound is set
  return {
    low: low ?? yMin,
    high: high ?? yMax,
  }
}

interface FlagDotProps {
  cx?: number
  cy?: number
  payload?: { flag?: MarkerFlag }
}

function FlagDot({ cx, cy, payload }: FlagDotProps) {
  if (cx === undefined || cy === undefined) return null
  const color = FLAG_COLORS[payload?.flag ?? 'unknown'] ?? FLAG_COLORS.unknown
  return <Dot cx={cx} cy={cy} r={4} fill={color} stroke="white" strokeWidth={1} />
}

export function MarkerHistoryChart({ canonicalName, displayName }: MarkerHistoryChartProps) {
  const { data: points, isLoading, isError } = useMarkerHistory(canonicalName)
  const { data: treatments = [] } = useTreatments()

  const [pinned, setPinnedState] = useState<boolean>(() => getPinned().includes(canonicalName))

  function togglePin() {
    const current = getPinned()
    let next: string[]
    if (pinned) {
      next = current.filter((c) => c !== canonicalName)
    } else {
      next = [...current, canonicalName]
    }
    setPinned(next)
    setPinnedState(!pinned)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return <p className="py-4 text-sm text-destructive">Failed to load marker history.</p>
  }

  const numericPoints = (points ?? []).filter((p) => p.value !== null)

  if (numericPoints.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8">
        <p className="text-sm text-muted-foreground">No numeric data for this marker.</p>
      </div>
    )
  }

  const values = numericPoints.map((p) => p.value as number)
  const yMin = Math.min(...values)
  const yMax = Math.max(...values)
  const padding = (yMax - yMin) * 0.15 || 1
  const domainMin = yMin - padding
  const domainMax = yMax + padding

  const refBand = computeRefBand(numericPoints, domainMin, domainMax)

  const chartData = numericPoints.map((p) => ({
    date: p.lab_date.slice(5), // MM-DD display
    fullDate: p.lab_date,
    value: p.value,
    flag: p.flag,
    unit: p.unit,
  }))

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{displayName ?? canonicalName}</p>
        <button
          type="button"
          onClick={togglePin}
          className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted"
          aria-label={pinned ? 'Unpin from insights' : 'Pin to insights'}
        >
          {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
          {pinned ? 'Unpin' : 'Pin to insights'}
        </button>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis
            tick={{ fontSize: 10 }}
            domain={[domainMin, domainMax]}
          />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            content={({ payload }) => {
              if (!payload?.length) return null
              const p = payload[0].payload as { value: number; flag: string; unit: string | null; date: string }
              return (
                <div className="rounded-lg border border-border bg-background px-2 py-1 text-xs shadow-sm">
                  <p className="font-medium">{p.date}</p>
                  <p>{p.value}{p.unit ? ` ${p.unit}` : ''} &middot; {p.flag}</p>
                </div>
              )
            }}
          />

          {refBand.low !== null && refBand.high !== null && (
            <ReferenceArea
              y1={refBand.low}
              y2={refBand.high}
              fill="#6366f120"
              strokeOpacity={0}
            />
          )}

          {treatments.map((t) => (
            <ReferenceLine
              key={`t-start-${t.id}`}
              x={t.start_date.slice(5)}
              stroke="#6366f180"
              strokeDasharray="4 2"
              label={{ value: t.name.slice(0, 8), fontSize: 9, fill: '#6366f1' }}
            />
          ))}
          {treatments
            .filter((t) => t.end_date)
            .map((t) => (
              <ReferenceLine
                key={`t-end-${t.id}`}
                x={t.end_date!.slice(5)}
                stroke="#94a3b880"
                strokeDasharray="4 2"
              />
            ))}

          <Line
            type="monotone"
            dataKey="value"
            stroke="#6366f1"
            strokeWidth={2}
            dot={<FlagDot />}
            activeDot={{ r: 5 }}
            name={displayName ?? canonicalName}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
