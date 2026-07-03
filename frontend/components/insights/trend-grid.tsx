'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useInsightsTrends, useMarkerHistory } from '@/lib/api/hooks'
import { TrendCard } from './trend-card'
import type { TrendSeries } from '@/lib/api/types'

const PINNED_KEY = 'labs.pinnedMarkers'

function readPinned(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(PINNED_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    // Intentional swallow — same reasoning as marker-history-chart.tsx's
    // getPinned(), which owns writes to this same PINNED_KEY.
    return []
  }
}

function usePinnedMarkers(): string[] {
  const [pinned] = useState<string[]>(readPinned)
  return pinned
}

interface PinnedMarkerCardProps {
  canonicalName: string
}

function PinnedMarkerCard({ canonicalName }: PinnedMarkerCardProps) {
  const { data: points, isLoading } = useMarkerHistory(canonicalName)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const numericPoints = (points ?? []).filter((p) => p.value !== null)
  if (numericPoints.length === 0) return null

  const latest = numericPoints[numericPoints.length - 1]
  const trendSeries: TrendSeries = {
    key: canonicalName,
    label: canonicalName,
    category: 'lab',
    points: numericPoints.map((p) => ({
      date: p.lab_date,
      value: p.value,
      rolling_avg_7: null,
    })),
    current: latest.value,
    rolling_avg_7: null,
    delta_30d: null,
  }

  return <TrendCard series={trendSeries} />
}

interface Props {
  start: string
  end: string
}

export function TrendGrid({ start, end }: Props) {
  const { data, isLoading, isError } = useInsightsTrends(start, end)
  const pinnedMarkers = usePinnedMarkers()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return (
      <p className="py-4 text-sm text-destructive">
        Failed to load trend data.
      </p>
    )
  }

  if (!data || data.series.length === 0) {
    return (
      <p className="py-4 text-sm text-muted-foreground">No trend data available.</p>
    )
  }

  return (
    <div className="space-y-4">
      {pinnedMarkers.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Pinned lab markers</p>
          <div className="grid grid-cols-2 gap-2">
            {pinnedMarkers.map((canonical) => (
              <PinnedMarkerCard key={canonical} canonicalName={canonical} />
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        {data.series.map((s) => (
          <TrendCard key={s.key} series={s} />
        ))}
      </div>
    </div>
  )
}
