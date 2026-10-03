'use client'

import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceArea,
  ReferenceLine,
  Dot,
} from 'recharts'
import {
  Button,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
  FetchError,
} from '@f0rge/ui'
import { Loader2, Pin, PinOff } from 'lucide-react'
import { useMarkerHistory, useTreatments } from '@/lib/api/hooks'
import type { MarkerFlag } from '@/lib/api/types'
import { chartStroke } from '@/lib/ui/status'

interface MarkerHistoryChartProps {
  canonicalName: string
  displayName?: string
}

const FLAG_COLORS: Record<MarkerFlag, string> = {
  normal: chartStroke.muted,
  low: chartStroke[2],
  high: 'var(--destructive)',
  abnormal: chartStroke.warn,
  unknown: chartStroke.muted,
}

const PINNED_KEY = 'labs.pinnedMarkers'

function getPinned(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function setPinned(list: string[]) {
  try {
    localStorage.setItem(PINNED_KEY, JSON.stringify(list))
  } catch {
    // storage unavailable — pin is optional
  }
}

function computeRefBand(
  points: { ref_low: number | null; ref_high: number | null }[],
  yMin: number,
  yMax: number,
): { low: number | null; high: number | null } {
  const lows = points.map((p) => p.ref_low).filter((v): v is number => v !== null)
  const highs = points.map((p) => p.ref_high).filter((v): v is number => v !== null)
  const low = lows.length > 0 ? Math.min(...lows) : null
  const high = highs.length > 0 ? Math.max(...highs) : null

  if (low === null && high === null) return { low: null, high: null }
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
  const { data: points, isLoading, isError, refetch } = useMarkerHistory(canonicalName)
  const { data: treatments = [] } = useTreatments()

  const [pinned, setPinnedState] = useState<boolean>(() => getPinned().includes(canonicalName))

  function togglePin() {
    const current = getPinned()
    const next = pinned
      ? current.filter((c) => c !== canonicalName)
      : [...current, canonicalName]
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
    return (
      <FetchError message="Failed to load marker history." onRetry={() => refetch()} />
    )
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
    date: p.lab_date.slice(5),
    fullDate: p.lab_date,
    value: p.value,
    flag: p.flag,
    unit: p.unit,
  }))

  const chartConfig = {
    value: {
      label: displayName ?? canonicalName,
      color: chartStroke[1],
    },
  } satisfies ChartConfig

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{displayName ?? canonicalName}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={togglePin}
          aria-label={pinned ? 'Unpin from Signals' : 'Pin to Signals'}
        >
          {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
          {pinned ? 'Unpin' : 'Pin to Signals'}
        </Button>
      </div>

      <ChartContainer config={chartConfig} className="aspect-auto h-[220px] w-full">
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} domain={[domainMin, domainMax]} />
          <ChartTooltip
            content={
              <ChartTooltipContent
                labelFormatter={(_, payload) => {
                  const row = payload?.[0]?.payload as { fullDate?: string } | undefined
                  return row?.fullDate ?? ''
                }}
                formatter={(value, _name, item) => {
                  const row = item.payload as { unit: string | null; flag: string }
                  const unit = row.unit ? ` ${row.unit}` : ''
                  return [`${value}${unit} · ${row.flag}`, displayName ?? canonicalName]
                }}
              />
            }
          />

          {refBand.low !== null && refBand.high !== null && (
            <ReferenceArea
              y1={refBand.low}
              y2={refBand.high}
              fill={chartStroke[1]}
              fillOpacity={0.125}
              strokeOpacity={0}
            />
          )}

          {treatments.map((t) => (
            <ReferenceLine
              key={`t-start-${t.id}`}
              x={t.start_date.slice(5)}
              stroke={chartStroke[1]}
              strokeOpacity={0.5}
              strokeDasharray="4 2"
              label={{ value: t.name.slice(0, 8), fontSize: 9, fill: chartStroke[1] }}
            />
          ))}
          {treatments
            .filter((t) => t.end_date)
            .map((t) => (
              <ReferenceLine
                key={`t-end-${t.id}`}
                x={t.end_date!.slice(5)}
                stroke={chartStroke.muted}
                strokeOpacity={0.5}
                strokeDasharray="4 2"
              />
            ))}

          <Line
            type="monotone"
            dataKey="value"
            stroke="var(--color-value)"
            strokeWidth={2}
            dot={<FlagDot />}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ChartContainer>
    </div>
  )
}
